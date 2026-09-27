```
ict_funded_ea_pro
├─ analytics
│  ├─ daily_trade_analyzer.py
│  ├─ drawdown_analyzer.py
│  ├─ performance_metrics.py
│  ├─ profit_factor.py
│  ├─ setup_statistics.py
│  ├─ trade_statistics.py
│  └─ winrate_analyzer.py
├─ api
│  ├─ auth.py
│  ├─ main.py
│  ├─ routes
│  │  ├─ accounts.py
│  │  ├─ licenses.py
│  │  ├─ statistics.py
│  │  ├─ subscriptions.py
│  │  └─ trades.py
│  └─ websocket.py
├─ backtester
│  ├─ export_mt5_data.py
│  ├─ historical_tests
│  ├─ monte_carlo
│  ├─ optimization
│  ├─ reports
│  ├─ test_btc_diagnostics.py
│  ├─ test_btc_reject_breakdown.py
│  ├─ test_btc_score_distribution.py
│  ├─ test_btc_score_rejects.py
│  ├─ test_btc_sl_rejected_analysis.py
│  ├─ test_candle_patterns.py
│  ├─ test_confidence_score.py
│  ├─ test_csv_parser.py
│  ├─ test_csv_provider.py
│  ├─ test_daily_trade_analyzer.py
│  ├─ test_dynamic_risk.py
│  ├─ test_entry_manager.py
│  ├─ test_event_aggregator.py
│  ├─ test_event_execution_engine.py
│  ├─ test_execution_layer.py
│  ├─ test_finnhub_provider.py
│  ├─ test_fmp_provider.py
│  ├─ test_forexfactory_provider.py
│  ├─ test_forexfactory_scheduler.py
│  ├─ test_fundamental_analyzer.py
│  ├─ test_fundamental_entry_filter.py
│  ├─ test_fundamental_state.py
│  ├─ test_fvg.py
│  ├─ test_global_daily_frequency.py
│  ├─ test_health_check.py
│  ├─ test_htf_alignment.py
│  ├─ test_liquidity.py
│  ├─ test_liquidity_void.py
│  ├─ test_live_news_updater.py
│  ├─ test_losing_trades_analysis.py
│  ├─ test_loss_diagnostics.py
│  ├─ test_loss_reason_breakdown.py
│  ├─ test_market_structure.py
│  ├─ test_multi_symbol_execution.py
│  ├─ test_nasdaq_diagnostics.py
│  ├─ test_news_direct.py
│  ├─ test_news_filter.py
│  ├─ test_news_service.py
│  ├─ test_notifications.py
│  ├─ test_onboarding_state.py
│  ├─ test_order_blocks.py
│  ├─ test_overall_performance_analyzer.py
│  ├─ test_premium_discount.py
│  ├─ test_risk_layer.py
│  ├─ test_rr_comparison.py
│  ├─ test_run_analysis.py
│  ├─ test_scheduler.py
│  ├─ test_score_breakdown.py
│  ├─ test_score_engine.py
│  ├─ test_score_ranges.py
│  ├─ test_sessions.py
│  ├─ test_setup_funnel.py
│  ├─ test_setup_ranker.py
│  ├─ test_support_resistance.py
│  ├─ test_symbol_validator.py
│  ├─ test_telegram_onboarding.py
│  ├─ test_trade_manager.py
│  ├─ test_ustec_breakdown.py
│  ├─ test_ustec_entry_source_stats.py
│  ├─ test_volume_imbalance.py
│  └─ test_weekend_guard.py
├─ billing
│  ├─ invoices.py
│  ├─ payments.py
│  ├─ refunds.py
│  └─ renewals.py
├─ btc.txt
├─ columns.txt
├─ config
│  ├─ .env
│  ├─ secrets.py
│  └─ settings.py
├─ core_engine
│  ├─ analytics
│  │  ├─ daily_trade_analyzer.py
│  │  └─ overall_performance_analyzer.py
│  ├─ config
│  │  ├─ detection
│  │  │  ├─ candle_patterns.py
│  │  │  ├─ fair_value_gap.py
│  │  │  ├─ liquidity.py
│  │  │  ├─ liquidity_void.py
│  │  │  ├─ market_structure.py
│  │  │  ├─ order_blocks.py
│  │  │  ├─ premium_discount.py
│  │  │  ├─ support_resistance.py
│  │  │  └─ volume_imbalance.py
│  │  ├─ market_profiles.py
│  │  └─ trading_modes.py
│  ├─ events
│  │  ├─ event_bus.py
│  │  ├─ event_dispatcher.py
│  │  ├─ event_types.py
│  │  └─ __init__.py
│  ├─ execution
│  │  ├─ break_even.py
│  │  ├─ entry_manager.py
│  │  ├─ execution_engine.py
│  │  ├─ partial_close.py
│  │  ├─ trade_manager.py
│  │  └─ trailing_stop.py
│  ├─ filters
│  │  ├─ htf_bias_filter.py
│  │  ├─ htf_score_modifier.py
│  │  ├─ trade_quality_filter.py
│  │  └─ __init__.py
│  ├─ risk
│  │  ├─ account_profile.py
│  │  ├─ daily_loss_guard.py
│  │  ├─ drawdown_protection.py
│  │  ├─ funded_risk.py
│  │  ├─ global_trade_limiter.py
│  │  ├─ lot_calculator.py
│  │  ├─ max_loss_guard.py
│  │  ├─ risk_validator.py
│  │  ├─ symbol_validator.py
│  │  └─ weekend_guard.py
│  ├─ scoring
│  │  ├─ confidence_score.py
│  │  ├─ score_breakdown.py
│  │  ├─ score_engine.py
│  │  └─ setup_ranker.py
│  └─ sessions
│     ├─ killzones.py
│     ├─ london_session.py
│     └─ newyork_session.py
├─ data
│  ├─ processed
│  │  ├─ BTCUSDm_low_score_rejects.csv
│  │  ├─ BTCUSDm_M15_execution_events.csv
│  │  ├─ BTCUSDm_M15_execution_layer_result.csv
│  │  ├─ BTCUSDm_reject_breakdown.csv
│  │  ├─ BTCUSDm_SL_TOO_WIDE_ANALYSIS.csv
│  │  ├─ fundamental_analysis.csv
│  │  ├─ fundamental_state.json
│  │  ├─ global_daily_trade_frequency.csv
│  │  ├─ multi_symbol_execution_summary.csv
│  │  ├─ news_cache.csv
│  │  ├─ test_json_parser.json
│  │  ├─ USTEC_M15_execution_events.csv
│  │  ├─ USTEC_M15_execution_layer_result.csv
│  │  ├─ XAUUSD_M15_candle_patterns_result.csv
│  │  ├─ XAUUSD_M15_confidence_score_result.csv
│  │  ├─ XAUUSD_M15_daily_trade_analysis.csv
│  │  ├─ XAUUSD_M15_execution_events.csv
│  │  ├─ XAUUSD_M15_execution_layer_result.csv
│  │  ├─ XAUUSD_M15_fvg_result.csv
│  │  ├─ XAUUSD_M15_liquidity_result.csv
│  │  ├─ XAUUSD_M15_liquidity_void_result.csv
│  │  ├─ XAUUSD_M15_order_blocks_result.csv
│  │  ├─ XAUUSD_M15_overall_performance.csv
│  │  ├─ XAUUSD_M15_premium_discount_result.csv
│  │  ├─ XAUUSD_M15_rr_comparison.csv
│  │  ├─ XAUUSD_M15_score_breakdown.csv
│  │  ├─ XAUUSD_M15_sessions_result.csv
│  │  ├─ XAUUSD_M15_setup_ranker_result.csv
│  │  ├─ XAUUSD_M15_structure_result1.csv
│  │  ├─ XAUUSD_M15_support_resistance_result.csv
│  │  ├─ XAUUSD_M15_trade_manager_result.csv
│  │  ├─ XAUUSD_M15_volume_imbalance_result.csv
│  │  └─ XAUUSD_M15_weekend_guard_result.csv
│  └─ raw
│     ├─ BTCUSDm_M15.csv
│     ├─ news_events.csv
│     ├─ USTEC_M15.csv
│     └─ XAUUSD_M15.csv
├─ database
│  ├─ .env
│  ├─ backups
│  ├─ db_handler.py
│  ├─ migrations
│  ├─ models.py
│  └─ session.py
├─ debug.txt
├─ docker-compose.yml
├─ docs
│  ├─ api_docs.md
│  ├─ architecture.md
│  ├─ deployment.md
│  ├─ gold_results_v1.md
│  ├─ ict_rules.md
│  └─ user_guide.md
├─ funnel.txt
├─ LICENSE
├─ license_system
│  ├─ activation.py
│  ├─ expiry_checker.py
│  ├─ license_manager.py
│  ├─ plan_manager.py
│  └─ subscription_manager.py
├─ media
│  ├─ chart_capture.py
│  ├─ reports
│  └─ trade_images.py
├─ monitoring
│  └─ logs
│     ├─ errors.log
│     ├─ error_tracker.py
│     ├─ health_check.py
│     └─ notifications.py
├─ mt5_bridge
│  ├─ Experts
│  │  └─ ICT_Funded_EA.mq5
│  └─ Include
│     ├─ api_client.mqh
│     ├─ bridge_client.mqh
│     ├─ license_checker.mqh
│     └─ trade_sender.mqh
├─ multi_symbol_debug.txt
├─ multi_symbol_debug1.txt
├─ news_engine
│  ├─ calendar.py
│  ├─ event_aggregator.py
│  ├─ fundamental_analyzer.py
│  ├─ fundamental_state.py
│  ├─ impact_classifier.py
│  ├─ live_news_updater.py
│  ├─ news_cache.py
│  ├─ news_filter.py
│  ├─ news_service.py
│  ├─ parsers
│  │  ├─ csv_parser.py
│  │  ├─ json_parser.py
│  │  ├─ xml_parser.py
│  │  └─ __init__.py
│  ├─ post_news_confirmation.py
│  ├─ providers
│  │  ├─ base_provider.py
│  │  ├─ csv_provider.py
│  │  ├─ forexfactory_provider.py
│  │  └─ __init__.py
│  ├─ repositories
│  │  ├─ base_repository.py
│  │  ├─ csv_repository.py
│  │  └─ postgres_repository.py
│  ├─ scheduler.py
│  └─ tradingeconomics.py
├─ README.md
├─ requirements.txt
├─ score_breakdown.txt
├─ score_ranges.txt
├─ security
│  ├─ access_control.py
│  ├─ account_binding.py
│  ├─ anti_sharing.py
│  └─ encryption.py
├─ telegram_bot
│  ├─ admin_commands.py
│  ├─ alerts.py
│  ├─ bot.py
│  ├─ commands.py
│  ├─ onboarding.py
│  ├─ onboarding_state.py
│  ├─ screenshots.py
│  └─ subscriptions.py
├─ tests
│  ├─ integration_tests
│  ├─ stress_tests
│  └─ unit_tests
└─ web_dashboard
   ├─ admin_dashboard
   │  ├─ analytics
   │  ├─ licenses
   │  ├─ monitoring
   │  ├─ revenue
   │  ├─ subscriptions
   │  ├─ support
   │  └─ users
   └─ client_dashboard
      ├─ overview
      ├─ risk
      ├─ statistics
      ├─ subscriptions
      └─ trades

```