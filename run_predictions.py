import pandas as pd
from src.evaluate import run

pred, true, recall = run("data/test.csv", "data/test")
pred.to_csv("outputs/test_predictions.csv", index=False)
print(pd.Series(recall).round(2))
