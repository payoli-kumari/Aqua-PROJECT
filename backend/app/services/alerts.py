# PROVISIONAL screening thresholds only.
# Confirm applicable CPCB/designated-best-use standards and parameter-specific
# sampling context with the project supervisor before presenting as compliance.
THRESHOLDS = {
    "BOD": {"warning_above": 3.0, "critical_above": 6.0},
    "DO": {"warning_below": 5.0, "critical_below": 4.0},
    "pH": {"warning_outside": [6.5, 8.5], "critical_outside": [6.0, 9.0]},
}

def assess(results):
    alerts = []
    for parameter, item in results.items():
        value = item["value"]
        rule = THRESHOLDS[parameter]
        severity = None
        if parameter == "BOD":
            severity = "critical" if value > rule["critical_above"] else ("warning" if value > rule["warning_above"] else None)
            msg = f"Predicted BOD is {value:.2f} mg/L."
        elif parameter == "DO":
            severity = "critical" if value < rule["critical_below"] else ("warning" if value < rule["warning_below"] else None)
            msg = f"Predicted dissolved oxygen is {value:.2f} mg/L."
        else:
            lo, hi = rule["warning_outside"]
            clo, chi = rule["critical_outside"]
            outside = value < lo or value > hi
            critical = value < clo or value > chi
            severity = "critical" if critical else ("warning" if outside else None)
            msg = f"Predicted pH is {value:.2f}."
        if severity:
            alerts.append({"parameter": parameter, "severity": severity, "message": msg,
                           "basis": "Provisional screening threshold; verify against applicable standard and observed sample."})
    return alerts
