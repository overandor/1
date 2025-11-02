"""Alpha Signal Radar service for Gate.io perpetual swap markets."""

from __future__ import annotations

import argparse
import os
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional

import ccxt
import numpy as np
import pandas as pd

HF_TOKEN = os.getenv("HF_TOKEN")
DEFAULT_OUTPUT_HTML = Path("alpha_signal_radar.html")
DIST_DIR = Path("alpha_signal_dist")
ZIP_PATH = Path("alpha_signal_radar.zip")


def log(msg: str) -> None:
    """Print a timestamped log message."""

    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}")


class AlphaConfig:
    """Configuration inputs for calculating actionable market signals."""

    def __init__(
        self,
        min_spread: float = 0.4,
        min_volume: float = 200_000,
        min_score: float = 60.0,
        imbalance_threshold: float = 0.2,
        momentum_lookback: int = 6,
        refresh_minutes: int = 3,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.min_spread = min_spread
        self.min_volume = min_volume
        self.min_score = min_score
        self.imbalance_threshold = imbalance_threshold
        self.momentum_lookback = momentum_lookback
        self.refresh_minutes = refresh_minutes
        self.weights = weights or {
            "spread": 0.25,
            "imbalance": 0.25,
            "momentum": 0.25,
            "volatility": 0.15,
            "liquidity": 0.10,
        }

    def normalized_weights(self) -> Dict[str, float]:
        """Return weights normalized to sum to one."""

        total = sum(self.weights.values()) or 1.0
        return {key: value / total for key, value in self.weights.items()}


def compute_alpha_components(
    ticker: Dict,
    orderbook: Dict,
    ohlcv: List[List[float]],
    config: AlphaConfig,
) -> Optional[Dict[str, float]]:
    """Derive alpha components from raw market data."""

    bids = orderbook.get("bids") or []
    asks = orderbook.get("asks") or []
    if not bids or not asks:
        return None

    best_bid = bids[0][0]
    best_ask = asks[0][0]
    last_price = ticker.get("last") or (best_bid + best_ask) / 2
    if not last_price:
        return None

    mid_price = (best_bid + best_ask) / 2
    spread = best_ask - best_bid
    spread_pct = (spread / mid_price) * 100 if mid_price else 0.0

    bid_depth = sum(level[1] for level in bids[:10])
    ask_depth = sum(level[1] for level in asks[:10])
    total_depth = bid_depth + ask_depth
    depth_imbalance = ((bid_depth - ask_depth) / total_depth) if total_depth else 0.0

    volume_24h = ticker.get("quoteVolume", 0.0)
    liquidity_factor = min(volume_24h / max(config.min_volume, 1.0), 5.0)

    closes = [row[4] for row in ohlcv if len(row) >= 5]
    momentum_change = 0.0
    if len(closes) >= config.momentum_lookback + 1:
        reference_price = closes[-(config.momentum_lookback + 1)]
        if reference_price:
            momentum_change = (closes[-1] / reference_price) - 1

    volatility = (np.std(closes) / np.mean(closes) * 100) if closes else 0.0

    weights = config.normalized_weights()
    spread_edge = max(0.0, (config.min_spread - spread_pct) / max(config.min_spread, 1e-6))
    imbalance_edge = max(0.0, abs(depth_imbalance) - config.imbalance_threshold)
    momentum_edge = abs(momentum_change)
    volatility_edge = max(0.0, (5.0 - volatility) / 5.0)
    liquidity_edge = min(1.0, liquidity_factor)

    alpha_score = 100 * (
        spread_edge * weights["spread"]
        + imbalance_edge * weights["imbalance"]
        + momentum_edge * weights["momentum"]
        + volatility_edge * weights["volatility"]
        + liquidity_edge * weights["liquidity"]
    )

    edge_notes = []
    if spread_pct <= config.min_spread:
        edge_notes.append("Tight Spread")
    if depth_imbalance >= config.imbalance_threshold:
        edge_notes.append("Bid Dominance")
    elif depth_imbalance <= -config.imbalance_threshold:
        edge_notes.append("Ask Dominance")
    if momentum_change >= 0.01:
        edge_notes.append("Bullish Momentum")
    elif momentum_change <= -0.01:
        edge_notes.append("Bearish Momentum")
    if volatility <= 2.5:
        edge_notes.append("Low Vol Regime")

    if alpha_score >= 80:
        conviction = "High Conviction"
    elif alpha_score >= config.min_score:
        conviction = "Watchlist"
    else:
        conviction = "Low"

    return {
        "price": last_price,
        "mid_price": mid_price,
        "spread_pct": spread_pct,
        "volume_24h": volume_24h,
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "total_depth": total_depth,
        "depth_imbalance": depth_imbalance,
        "momentum_change": momentum_change * 100,
        "volatility": volatility,
        "liquidity_factor": liquidity_factor,
        "alpha_score": round(alpha_score, 2),
        "edge_notes": ", ".join(edge_notes) if edge_notes else "Neutral",
        "conviction": conviction,
    }


def fetch_alpha_dataframe(exchange: ccxt.Exchange, config: AlphaConfig) -> pd.DataFrame:
    """Fetch market data and build the alpha scoring dataframe."""

    markets = exchange.load_markets()
    usdt_pairs = [
        symbol
        for symbol, meta in markets.items()
        if "/USDT" in symbol and meta.get("type") == "swap"
    ]

    rows: List[Dict[str, float]] = []
    for symbol in usdt_pairs[:40]:
        try:
            ticker = exchange.fetch_ticker(symbol)
            orderbook = exchange.fetch_order_book(symbol, limit=20)
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=24)
        except Exception as exc:  # pragma: no cover - network issues
            log(f"⚠️ Data error [{symbol}]: {exc}")
            continue

        components = compute_alpha_components(ticker, orderbook, ohlcv, config)
        if not components:
            continue

        rows.append({"symbol": symbol, **components, "timestamp": datetime.now(UTC)})

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["depth_imbalance_pct"] = df["depth_imbalance"] * 100
    df.sort_values("alpha_score", ascending=False, inplace=True)
    return df


def render_html(df: pd.DataFrame, config: AlphaConfig, output_path: Path) -> None:
    """Render an HTML dashboard for the alpha signals."""

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    top = df.iloc[0]

    table_html = (
        df[
            [
                "symbol",
                "price",
                "spread_pct",
                "volume_24h",
                "depth_imbalance_pct",
                "momentum_change",
                "volatility",
                "alpha_score",
                "conviction",
                "edge_notes",
            ]
        ]
        .head(25)
        .rename(
            columns={
                "symbol": "Symbol",
                "price": "Price",
                "spread_pct": "Spread %",
                "volume_24h": "24h Volume",
                "depth_imbalance_pct": "Depth Imbalance %",
                "momentum_change": "Momentum %",
                "volatility": "Volatility %",
                "alpha_score": "Alpha Score",
                "conviction": "Conviction",
                "edge_notes": "Signal Notes",
            }
        )
        .to_html(index=False, classes="signal-table")
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Gate.io Alpha Signal Radar</title>
  <style>
    body {{
      font-family: "Trebuchet MS", sans-serif;
      background: #0f0f23;
      color: #f5f5ff;
      margin: 0;
      padding: 40px;
    }}
    h1 {{
      text-align: center;
      background: linear-gradient(90deg, #ff6b00, #ff8c42);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      font-size: 2.8rem;
      margin-bottom: 8px;
    }}
    .subtitle {{
      text-align: center;
      color: #b0b0ff;
      margin-bottom: 40px;
    }}
    .metrics {{
      display: flex;
      flex-wrap: wrap;
      gap: 20px;
      justify-content: center;
      margin-bottom: 30px;
    }}
    .metric-card {{
      background: linear-gradient(145deg, #1e1e3f, #2d2b55);
      border-radius: 16px;
      padding: 20px 26px;
      box-shadow: 5px 5px 18px rgba(0,0,0,0.3);
      border: 1px solid rgba(255, 107, 0, 0.35);
      min-width: 220px;
    }}
    .metric-card h3 {{
      margin: 0;
      font-size: 0.95rem;
      color: #aaa;
      letter-spacing: 0.04em;
    }}
    .metric-card p {{
      margin: 8px 0 0;
      font-size: 1.4rem;
      color: #fafafa;
    }}
    .signal-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 30px;
      background: rgba(9, 9, 20, 0.8);
      border-radius: 12px;
      overflow: hidden;
    }}
    .signal-table th, .signal-table td {{
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }}
    .signal-table th {{
      background: rgba(255, 107, 0, 0.25);
      color: #fff;
      font-weight: 600;
      letter-spacing: 0.05em;
    }}
    .signal-table tr:nth-child(even) {{
      background: rgba(255,255,255,0.04);
    }}
    .footer {{
      margin-top: 50px;
      text-align: center;
      font-size: 0.85rem;
      color: #8889b7;
    }}
  </style>
</head>
<body>
  <h1>Gate.io Alpha Signal Radar</h1>
  <div class="subtitle">Generated {generated_at} &middot; Thresholds: Spread &le; {config.min_spread:.2f}%, Volume ≥ {config.min_volume:,.0f} USDT</div>

  <div class="metrics">
    <div class="metric-card">
      <h3>Top Opportunity</h3>
      <p>{top['symbol']} &nbsp; · &nbsp; {top['alpha_score']:.1f}</p>
    </div>
    <div class="metric-card">
      <h3>Depth Imbalance</h3>
      <p>{top['depth_imbalance']*100:.1f}% ({top['edge_notes']})</p>
    </div>
    <div class="metric-card">
      <h3>Momentum ({config.momentum_lookback}h)</h3>
      <p>{top['momentum_change']:.2f}%</p>
    </div>
    <div class="metric-card">
      <h3>Spread</h3>
      <p>{top['spread_pct']:.2f}%</p>
    </div>
  </div>

  <section>
    <h2>Opportunity Table</h2>
    {table_html}
  </section>

  <div class="footer">
    Depth imbalance is (bid depth − ask depth) / total depth. Positive values indicate bid-side pressure.<br/>
    Signals are analytics only; verify execution suitability before trading.
  </div>
</body>
</html>
"""

    output_path.write_text(html, encoding="utf-8")
    log(f"📄 Wrote HTML report to {output_path.resolve()}")


def initialize_exchange(api_key: Optional[str], api_secret: Optional[str]) -> ccxt.gateio:
    """Create a Gate.io exchange client with swap defaults."""

    exchange = ccxt.gateio(
        {
            "apiKey": api_key or "",
            "secret": api_secret or "",
            "enableRateLimit": True,
            "options": {"defaultType": "swap", "defaultSettle": "usdt"},
        }
    )
    try:
        exchange.load_markets()
    except Exception as exc:  # pragma: no cover - network issues
        raise RuntimeError(f"Failed to load markets: {exc}") from exc
    return exchange


def package_report(html_path: Path, dist_dir: Path, zip_path: Path) -> None:
    """Prepare distributable artifacts for the generated report."""

    if dist_dir.exists():
        for item in dist_dir.iterdir():
            if item.is_file():
                item.unlink()
            else:
                for sub in item.rglob("*"):
                    if sub.is_file():
                        sub.unlink()
                item.rmdir()
    dist_dir.mkdir(parents=True, exist_ok=True)
    target = dist_dir / "index.html"
    target.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in dist_dir.rglob("*"):
            archive.write(file, file.relative_to(dist_dir))
    log(f"🗜️ Packaged report into {zip_path.resolve()}")


def generate_repo_name(prefix: str = "gateio-alpha") -> str:
    """Generate a timestamped Hugging Face space name."""

    now = datetime.now(UTC)
    return f"{prefix}-{now.strftime('%Y%m%d-%H%M%S')}"


def deploy_to_huggingface(repo_id: str, source_dir: Path, token: str) -> None:
    """Deploy the generated report to a Hugging Face static space."""

    try:
        from huggingface_hub import HfApi, HfFolder, upload_folder
        from huggingface_hub.utils import HfHubHTTPError
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "huggingface_hub package is required for --deploy. "
            "Install it via 'pip install huggingface-hub'."
        ) from exc

    api = HfApi()
    HfFolder.save_token(token)

    try:
        api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="static")
        log(f"📦 Created Hugging Face space: {repo_id}")
        time.sleep(3)
    except HfHubHTTPError as exc:
        if "Conflict" in str(exc):
            log("⚠️ Repo already exists, continuing...")
        else:
            raise

    upload_folder(
        folder_path=str(source_dir),
        repo_id=repo_id,
        repo_type="space",
        token=token,
        commit_message="Upload alpha signal report",
    )
    log(f"✅ Deployed to https://huggingface.co/spaces/{repo_id}")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for report generation."""

    parser = argparse.ArgumentParser(
        description="Gate.io Alpha Signal Radar (HTML)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_HTML,
        help="Output HTML path",
    )
    parser.add_argument(
        "--min-spread",
        type=float,
        default=0.4,
        help="Maximum spread threshold (%)",
    )
    parser.add_argument(
        "--min-volume",
        type=float,
        default=200_000,
        help="Minimum 24h quote volume (USDT)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=60.0,
        help="Minimum alpha score for display",
    )
    parser.add_argument(
        "--imbalance",
        type=float,
        default=0.2,
        help="Depth imbalance threshold",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=6,
        help="Momentum lookback in hours",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy generated report to Hugging Face Space",
    )
    parser.add_argument(
        "--repo-prefix",
        type=str,
        default="gateio-alpha",
        help="Prefix for HF repo name",
    )
    parser.add_argument(
        "--gate-api-key",
        type=str,
        default=os.getenv("GATE_API_KEY"),
        help="Gate.io API key",
    )
    parser.add_argument(
        "--gate-api-secret",
        type=str,
        default=os.getenv("GATE_API_SECRET"),
        help="Gate.io API secret",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """Entry-point for generating the Gate.io alpha signal report."""

    args = parse_args(argv)

    config = AlphaConfig(
        min_spread=args.min_spread,
        min_volume=args.min_volume,
        min_score=args.min_score,
        imbalance_threshold=args.imbalance,
        momentum_lookback=args.lookback,
    )

    try:
        exchange = initialize_exchange(args.gate_api_key, args.gate_api_secret)
    except RuntimeError as exc:  # pragma: no cover - network issues
        log(f"❌ Exchange init failed: {exc}")
        sys.exit(1)

    df = fetch_alpha_dataframe(exchange, config)
    if df.empty:
        log("⚠️ No qualifying symbols met the criteria; nothing to render.")
        sys.exit(0)

    render_html(df, config, args.output)

    if args.deploy:
        if not HF_TOKEN:
            log("❌ HF_TOKEN environment variable not set; cannot deploy.")
            sys.exit(1)

        package_report(args.output, DIST_DIR, ZIP_PATH)
        repo_id = generate_repo_name(args.repo_prefix)
        try:
            deploy_to_huggingface(repo_id, DIST_DIR, HF_TOKEN)
        except Exception as exc:  # pragma: no cover - network issues
            log(f"❌ Deployment failed: {exc}")
            sys.exit(1)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
