def format_currency(value):
    """Placeholder for currency formatting if needed later."""
    try:
        return f"₹{value:,.2f}" 
    except (TypeError, ValueError):
        return str(value)