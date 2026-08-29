from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def format_zar(amount: float) -> str:
    return f"R{amount:,.2f}"


def format_zar_compact(amount: float) -> str:
    if amount >= 1000000:
        return f"R{amount/1000000:.1f}M"
    elif amount >= 1000:
        return f"R{amount/1000:.0f}k"
    return f"R{amount:.0f}"


templates.env.filters["format_zar"] = format_zar
templates.env.filters["format_zar_compact"] = format_zar_compact
