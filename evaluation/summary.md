# Evaluation results

Model: `gemini-3.5-flash-lite` (free tier). 14 of 14 reports generated.

| Version | Numbers supported by the analysis | Share |
|---|---|---|
| Baseline: plain prompt, no fact sheet (the original app) | 444 / 476 | 93.3% |
| With fact sheet and JSON claims, first draft | 550 / 578 | 95.2% |
| After the correction pass (what the app shows) | 544 / 544 | 100.0% |

Correction pass used in 6 of 14 reports.

| Dataset | Style | Baseline | First draft | Final |
|---|---|---|---|---|
| sales_performance_2023.csv | executive_summary | 24/24 | 42/42 | 42/42 |
| sales_performance_2023.csv | detailed_analysis | 49/51 | 57/57 | 57/57 |
| sales_data.csv | executive_summary | 22/23 | 30/30 | 30/30 |
| sales_data.csv | detailed_analysis | 42/47 | 43/43 | 43/43 |
| marketing_campaigns_2023.csv | executive_summary | 20/20 | 37/38 | 36/36 |
| marketing_campaigns_2023.csv | detailed_analysis | 44/50 | 59/67 | 51/51 |
| marketing_performance_2023.csv | executive_summary | 25/25 | 40/40 | 40/40 |
| marketing_performance_2023.csv | detailed_analysis | 34/37 | 76/76 | 76/76 |
| marketing_data.csv | executive_summary | 15/15 | 24/24 | 24/24 |
| marketing_data.csv | detailed_analysis | 33/35 | 41/42 | 41/41 |
| financial_kpis_2022_2023.csv | executive_summary | 21/21 | 16/16 | 16/16 |
| financial_kpis_2022_2023.csv | detailed_analysis | 44/48 | 37/43 | 38/38 |
| financial_performance_2022_2023.csv | executive_summary | 21/22 | 18/20 | 18/18 |
| financial_performance_2022_2023.csv | detailed_analysis | 50/58 | 30/40 | 32/32 |
