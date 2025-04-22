def parse_expense(response):
    doc = response["ExpenseDocuments"][0]
    summary = { f["Type"]["Text"]: f["ValueDetection"]["Text"]
                for f in doc["SummaryFields"] }

    items = []
    for grp in doc.get("LineItemGroups", []):
        for li in grp["LineItems"]:
            items.append({
                "name": li["LineItemExpenseFields"][0]["ValueDetection"]["Text"],
                "price": li["LineItemExpenseFields"][-1]["ValueDetection"]["Text"]
            })

    return {
        "vendor": summary.get("VENDOR_NAME"),
        "date":   summary.get("INVOICE_RECEIPT_DATE"),
        "total":  summary.get("TOTAL"),
        "items":  items
    }