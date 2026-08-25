"""Local web viewer for historical trending star reports."""

from flask import Flask, render_template, request, send_from_directory

import api
import db
import i18n
from period import TIME_RANGES


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.sort_keys = False
    i18n.register(app)
    api.register(app)

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            app.static_folder,
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

    @app.route("/")
    def index():
        time_range = request.args.get("range", "weekly")
        if time_range not in TIME_RANGES:
            time_range = "weekly"

        periods = db.list_periods(time_range)
        selected = request.args.get("period")
        if selected and not any(item["period_key"] == selected for item in periods):
            selected = None
        if not selected and periods:
            selected = periods[0]["period_key"]

        report = db.get_report(time_range, selected) if selected else None
        prev_period, next_period = _neighbors(periods, selected)
        lang = i18n.current_lang()
        periods, report = i18n.localize_period_labels(
            time_range, periods, report, lang
        )

        return render_template(
            "report.html",
            time_range=time_range,
            ranges=TIME_RANGES,
            range_labels=i18n.range_labels(lang),
            periods=periods,
            selected=selected,
            report=report,
            prev_period=prev_period,
            next_period=next_period,
            stars_label=i18n.stars_label(lang, time_range),
            active_nav="reports",
        )

    return app


def _neighbors(periods: list[dict], selected: str | None) -> tuple[str | None, str | None]:
    """Return older / newer period keys around the selected period."""
    if not selected:
        return None, None
    keys = [item["period_key"] for item in periods]
    try:
        index = keys.index(selected)
    except ValueError:
        return None, None
    newer = keys[index - 1] if index > 0 else None
    older = keys[index + 1] if index + 1 < len(keys) else None
    return older, newer


def run_web(host: str = "0.0.0.0", port: int = 8765) -> None:
    db.init_db()
    app = create_app()
    print(f"History viewer: http://127.0.0.1:{port}")
    app.run(host=host, port=port, debug=False)
