def format_currency(value):
    """Placeholder for currency formatting if needed later."""
    try:
        return f"₹{value:,.2f}" # Example: Indian Rupee format
    except (TypeError, ValueError):
        return str(value)