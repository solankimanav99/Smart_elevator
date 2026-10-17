"""Safety logic — determines elevator status from weight vs limit."""

def get_status(weight, limit, human_detected=False):
    if limit <= 0:
        return "UNKNOWN", "No limit set", "#888888"
    
    ratio = weight / limit
    
    if ratio > 1.0:
        if human_detected:
            return "HIGH RISK", "Person detected during overload!", "#ff0000"
        return "OVERLOAD", "Limit exceeded — take action", "#ff4444"
    elif ratio >= 0.7:
        return "WARNING", "Approaching load limit", "#ffaa00"
    else:
        return "SAFE", "Within safe load capacity", "#00cc66"
