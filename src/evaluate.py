import os, time
import pandas as pd
from src.loader import load_text
from src.extractor import extract_fields, CSV_COLUMNS


def find_file(folder, file_id):
    for f in os.listdir(folder):
        if f.split("-")[0] == file_id:
            return os.path.join(folder, f)
    return None


def norm(v):
    """Make true and predicted values comparable (no extraction logic here)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    try:  # 30.0 and 30 and "30" all become "30"
        return str(int(float(s)))
    except ValueError:
        return s


def run(csv_path, folder, delay=2):
    df = pd.read_csv(csv_path)
    preds, rows = [], []
    for _, row in df.iterrows():
        file_id = row["File Name"].split("-")[0]
        path = find_file(folder, file_id)
        if path is None:
            print("skipping (file not in folder):", row["File Name"])
            continue
        pred = extract_fields(load_text(path))
        out = {"File Name": row["File Name"]}
        for key, col in CSV_COLUMNS.items():
            out[col] = pred[key]
        preds.append(out)
        rows.append(row)
        time.sleep(delay)  # be gentle with the free-tier rate limit
    pred_df = pd.DataFrame(preds)
    true_df = pd.DataFrame(rows).reset_index(drop=True)

    recall = {}
    for col in CSV_COLUMNS.values():
        hits = [norm(t) == norm(p) for t, p in zip(true_df[col], pred_df[col])]
        recall[col] = sum(hits) / len(hits)
    return pred_df, true_df, recall
