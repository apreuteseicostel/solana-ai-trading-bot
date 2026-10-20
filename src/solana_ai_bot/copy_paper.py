"""Paper-only fixed-size USDC copy experiment with conservative quote fills.

This is independently written code, not copied from SolTrade or Gateway.
An observed SELL closes this experiment's entire matching position; it does
not claim to reconstruct the whale's unknown portfolio or realized P&L.
"""

from dataclasses import asdict, dataclass

from .intel_models import USDC, Quote, WalletEvent, integer


@dataclass(frozen=True)
class CopyConfig:
    starting_cash_raw: int = 1_000_000_000
    trade_size_raw: int = 25_000_000
    max_position_cost_raw: int = 100_000_000
    max_total_cost_raw: int = 300_000_000
    max_positions: int = 5
    max_signal_age_seconds: int = 120
    min_copy_delay_seconds: int = 2
    max_quote_age_seconds: int = 15
    max_impact_bps: int = 100
    max_drawdown_bps: int = 1000
    max_daily_loss_raw: int = 50_000_000
    estimated_network_fee_raw: int = 10_000
    extra_fee_bps: int = 0

    def __post_init__(self):
        for value in asdict(self).values():
            if type(value) is not int:
                raise TypeError("Paper configuration uses integer atomic units")
            integer(value)
        for value in (
            self.starting_cash_raw,
            self.trade_size_raw,
            self.max_positions,
            self.max_signal_age_seconds,
            self.max_quote_age_seconds,
            self.max_drawdown_bps,
            self.max_daily_loss_raw,
        ):
            integer(value, positive=True)
        if (
            self.max_drawdown_bps > 10000
            or self.extra_fee_bps > 1000
            or self.max_impact_bps > 10000
        ):
            raise ValueError("Invalid risk percentage")
        if self.max_positions > 100 or self.estimated_network_fee_raw == 0:
            raise ValueError("Position limit too high or missing network cost estimate")


def position_key(event, mint):
    return event.wallet + ":" + mint


class CopyPaper:
    def __init__(self, store, run_id="default", config=None):
        if not isinstance(run_id, str) or not 1 <= len(run_id) <= 80:
            raise ValueError("Invalid run id")
        self.store, self.run_id = store, run_id
        with store.transaction():
            existing = store.run(run_id)
            self.config = (
                CopyConfig(**existing[0])
                if existing and config is None
                else config or CopyConfig()
            )
            if existing and existing[0] != asdict(self.config):
                raise ValueError(
                    "Existing run configuration is immutable; choose a new run id"
                )
            if not existing:
                cash = self.config.starting_cash_raw
                store.save_run(
                    run_id,
                    asdict(self.config),
                    {
                        "cash_raw": cash,
                        "positions": {},
                        "realized_pnl_raw": 0,
                        "peak_equity_raw": cash,
                        "max_drawdown_bps": 0,
                        "halted": False,
                        "last_time": 0,
                        "day": None,
                        "day_realized_start_raw": 0,
                        "estimated_network_cost_raw": 0,
                        "extra_fee_raw": 0,
                        "slippage_output_haircut_raw": {},
                        "dataset_mode": None,
                    },
                )

    def state(self):
        return self.store.run(self.run_id)[1]

    def request_for(self, event, state=None):
        """Return required quote only for supported USDC/token swaps."""
        state = state or self.state()
        if event.kind != "swap":
            return None
        if event.input_mint == USDC:
            return USDC, event.output_mint, self.config.trade_size_raw
        if event.output_mint == USDC:
            position = state["positions"].get(position_key(event, event.input_mint))
            if position:
                return event.input_mint, USDC, position["quantity_raw"]
        return None

    def process(
        self, event: WalletEvent, quote: Quote | None, *, now: int, failure=None
    ):
        integer(now)
        with self.store.transaction():
            previous = self.store.decision(self.run_id, event)
            if previous:
                return previous
            state = self.state()
            result = self._process(event, quote, now, state, failure)
            self.store.save_run(self.run_id, asdict(self.config), state)
            self.store.save_decision(self.run_id, event, result)
            if quote:
                self.store.add_quote(quote)
            return result

    def _process(self, event, quote, now, state, failure):
        config = self.config
        result = {
            "wallet": event.wallet,
            "signature": event.signature,
            "at": now,
            "source": event.source,
            "mode": "paper",
            "status": "rejected",
            "block_time": event.block_time,
            "observed_at": event.observed_at,
            "latency_seconds": now - event.block_time,
        }

        def reject(reason):
            result["reason"] = reason
            return result

        mode = (
            "forward_observations"
            if event.source == "helius_parsed_events"
            else event.source
        )
        if state["dataset_mode"] not in (None, mode):
            return reject("mixed_data_sources_use_separate_run")
        state["dataset_mode"] = mode
        if now < max(event.observed_at, state["last_time"]):
            return reject("time_moved_backwards")
        state["last_time"] = now
        day = now // 86400
        if state["day"] != day:
            state["day"] = day
            state["day_realized_start_raw"] = state["realized_pnl_raw"]
        if event.kind != "swap":
            return reject(event.reason)
        if now - event.block_time > config.max_signal_age_seconds:
            return reject("stale_signal")
        if now < event.observed_at + config.min_copy_delay_seconds:
            return reject("copy_delay_not_elapsed")
        request = self.request_for(event, state)
        if request is None:
            return reject("unsupported_pair_or_no_paper_position")
        if failure:
            return reject(failure)
        if quote is None:
            return reject("missing_quote")
        expected_source = (
            "jupiter_v2" if mode == "forward_observations" else event.source
        )
        if quote.source != expected_source:
            return reject("quote_source_does_not_match_experiment")
        if (quote.input_mint, quote.output_mint, quote.input_raw) != request:
            return reject("quote_does_not_match_order")
        if (
            not event.observed_at + config.min_copy_delay_seconds
            <= quote.fetched_at
            <= now
        ):
            return reject("quote_predates_copy_or_is_from_future")
        if now - quote.fetched_at > config.max_quote_age_seconds:
            return reject("stale_quote")
        buy = request[0] == USDC
        if buy and abs(quote.price_impact_pct) * 100 > config.max_impact_bps:
            return reject("price_impact_limit")
        mint = request[1] if buy else request[0]
        key = position_key(event, mint)
        position = state["positions"].get(key)
        if buy:
            if state["halted"]:
                return reject("drawdown_halt")
            daily = state["realized_pnl_raw"] - state["day_realized_start_raw"]
            if daily <= -config.max_daily_loss_raw:
                return reject("daily_loss_limit")
            if position is None and len(state["positions"]) >= config.max_positions:
                return reject("position_count_limit")
            # New exposure requires fresh liquidation marks for every existing position.
            if any(
                p.get("marked_at") is None
                or p["marked_at"] < now - config.max_quote_age_seconds
                for p in state["positions"].values()
            ):
                return reject("fresh_liquidation_marks_required")
            fee = request[2] * config.extra_fee_bps // 10000
            cost = request[2] + fee + config.estimated_network_fee_raw
            exposure = sum(p["cost_raw"] for p in state["positions"].values())
            if cost > state["cash_raw"]:
                return reject("insufficient_paper_cash")
            if (
                cost + (position or {}).get("cost_raw", 0)
                > config.max_position_cost_raw
            ):
                return reject("position_exposure_limit")
            if exposure + cost > config.max_total_cost_raw:
                return reject("total_exposure_limit")
            state["cash_raw"] -= cost
            state["positions"][key] = {
                "wallet": event.wallet,
                "mint": mint,
                "quantity_raw": (position or {}).get("quantity_raw", 0)
                + quote.minimum_output_raw,
                "cost_raw": (position or {}).get("cost_raw", 0) + cost,
                # Cost is not an executable liquidation mark.
                "liquidation_raw": None,
                "marked_at": None,
            }
            result.update(
                side="BUY",
                input_raw=request[2],
                output_raw=quote.minimum_output_raw,
                position_mint=mint,
                realized_pnl_raw=0,
            )
        else:
            # Risk stops never prevent a supported exit from reducing exposure.
            fee = quote.minimum_output_raw * config.extra_fee_bps // 10000
            proceeds = quote.minimum_output_raw - fee - config.estimated_network_fee_raw
            if proceeds < 0:
                return reject("exit_cost_exceeds_proceeds")
            pnl = proceeds - position["cost_raw"]
            state["cash_raw"] += proceeds
            state["realized_pnl_raw"] += pnl
            del state["positions"][key]
            result.update(
                side="SELL",
                input_raw=request[2],
                output_raw=quote.minimum_output_raw,
                position_mint=mint,
                realized_pnl_raw=pnl,
            )
        state["estimated_network_cost_raw"] += config.estimated_network_fee_raw
        state["extra_fee_raw"] += fee
        haircuts = state["slippage_output_haircut_raw"]
        haircuts[quote.output_mint] = haircuts.get(quote.output_mint, 0) + (
            quote.output_raw - quote.minimum_output_raw
        )
        result.update(
            status="filled",
            reason="conservative_quote_simulation",
            quote=quote.record(),
            costs={
                "estimated_network_usdc_raw": config.estimated_network_fee_raw,
                "extra_fee_usdc_raw": fee,
                "slippage_haircut_output_raw": quote.output_raw
                - quote.minimum_output_raw,
                "route_fees_and_price_impact": "already_embedded_in_quote_output",
                "network_cost_source": "user_configured_estimate_not_actual_chain_fee",
            },
        )
        self._risk(state, now)
        return result

    def mark(self, key, quote, *, now):
        """Revalue a whole position at conservative USDC liquidation proceeds."""
        integer(now)
        with self.store.transaction():
            state = self.state()
            position = state["positions"][key]
            expected_source = (
                "jupiter_v2"
                if state["dataset_mode"] == "forward_observations"
                else state["dataset_mode"]
            )
            if quote.source != expected_source:
                raise ValueError("Quote source does not match experiment")
            if (
                (quote.input_mint, quote.output_mint, quote.input_raw)
                != (position["mint"], USDC, position["quantity_raw"])
                or not state["last_time"] <= now
                or not 0 <= now - quote.fetched_at <= self.config.max_quote_age_seconds
            ):
                raise ValueError("Invalid liquidation mark")
            fee = quote.minimum_output_raw * self.config.extra_fee_bps // 10000
            position["liquidation_raw"] = max(
                0,
                quote.minimum_output_raw - fee - self.config.estimated_network_fee_raw,
            )
            position["marked_at"] = quote.fetched_at
            state["last_time"] = now
            self._risk(state, now)
            self.store.add_quote(quote)
            self.store.save_run(self.run_id, asdict(self.config), state)

    def _risk(self, state, now):
        equity = self.equity(state, now)
        if equity is None:
            return
        state["peak_equity_raw"] = max(state["peak_equity_raw"], equity)
        peak = state["peak_equity_raw"]
        drawdown = (peak - equity) * 10000 // peak
        state["max_drawdown_bps"] = max(state["max_drawdown_bps"], drawdown)
        if drawdown >= self.config.max_drawdown_bps:
            state["halted"] = True

    def equity(self, state, now):
        if any(
            p["liquidation_raw"] is None
            or p["marked_at"] is None
            or not 0 <= now - p["marked_at"] <= self.config.max_quote_age_seconds
            for p in state["positions"].values()
        ):
            return None
        return state["cash_raw"] + sum(
            p["liquidation_raw"] for p in state["positions"].values()
        )

    def report(self, *, now):
        state = self.state()
        equity = self.equity(state, now)
        invested = sum(p["cost_raw"] for p in state["positions"].values())
        return {
            "mode": "paper",
            "live_execution_available": False,
            "run_id": self.run_id,
            "unit": "USDC",
            "atomic_units_per_usdc": 1_000_000,
            "equity_raw": equity,
            "equity_status": "fresh_quote_marks"
            if equity is not None
            else "unknown_until_all_positions_have_fresh_liquidation_quotes",
            "unrealized_pnl_raw": None
            if equity is None
            else equity - state["cash_raw"] - invested,
            "config": asdict(self.config),
            "state": state,
            "recent_decisions": self.store.decisions(self.run_id),
        }
