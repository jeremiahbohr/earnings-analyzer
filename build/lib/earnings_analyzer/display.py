def display_snapshot(snapshot_data):
    """
    Displays the formatted company snapshot.
    """
    print("\n=========================================")
    print(f"Company Snapshot: {snapshot_data['profile'].get('companyName')} ({snapshot_data['profile'].get('symbol')})")
    print("=========================================")

    print("\n[-- Profile --]")
    print(f"Sector: {snapshot_data['profile'].get('sector')}")
    print(f"Industry: {snapshot_data['profile'].get('industry')}")

    print("\n[-- Earnings Call Sentiment --]")
    print(f"Overall Sentiment Score: {snapshot_data['sentiment'].get('overall_sentiment_score')}/10")
    print(f"Confidence Level: {snapshot_data['sentiment'].get('confidence_level') * 100:.0f}%")
    print("Key Insights:")
    for theme in snapshot_data['sentiment'].get('key_themes', []):
        print(f"- {theme}")

    if 'stock_performance' in snapshot_data and snapshot_data['stock_performance']:
        perf = snapshot_data['stock_performance']
        print("\n[-- Stock Performance (Post-Call) --]")
        print(f"Price at Call: {perf['price_at_call']:.2f}")
        if perf['performance_1_week'] is not None:
            print(f"1 Week Performance: {perf['performance_1_week']:.2%}")
        if perf['performance_1_month'] is not None:
            print(f"1 Month Performance: {perf['performance_1_month']:.2%}")
        if perf['performance_3_month'] is not None:
            print(f"3 Month Performance: {perf['performance_3_month']:.2%}")

    