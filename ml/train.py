"""Train a demonstration model on Kaggle education leads, never customer records."""
import argparse
import hashlib
import json
from pathlib import Path
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', type=Path, default=root / 'data/raw/kaggle_lead_scoring/Leads X Education.csv')
    parser.add_argument('--output', type=Path, default=root / 'ml/artifacts')
    args = parser.parse_args()
    data = pd.read_csv(args.csv)
    numeric = ['TotalVisits', 'Total Time Spent on Website', 'Page Views Per Visit']
    categorical = ['Lead Source']
    features = numeric + categorical
    if not set(features + ['Converted', 'Prospect ID']).issubset(data.columns):
        raise ValueError('Dataset does not match the supported Kaggle schema.')
    data = data.drop_duplicates(subset=['Prospect ID']).copy()
    for field in numeric:
        data[field] = pd.to_numeric(data[field], errors='coerce')
        data.loc[data[field] < 0, field] = float('nan')
    data['Lead Source'] = data['Lead Source'].replace('Select', float('nan'))
    if not set(data['Converted'].unique()) <= {0, 1}:
        raise ValueError('Converted must contain binary labels.')
    X_train, X_test, y_train, y_test = train_test_split(data[features], data['Converted'], test_size=0.2, random_state=42, stratify=data['Converted'])
    prep = ColumnTransformer([
        ('numeric', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), numeric),
        ('categorical', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('encode', OneHotEncoder(handle_unknown='ignore'))]), categorical),
    ])
    pipeline = Pipeline([('preprocess', prep), ('model', LogisticRegression(max_iter=2000, random_state=42))])
    pipeline.fit(X_train, y_train)
    probabilities = pipeline.predict_proba(X_test)[:, 1]
    digest = hashlib.sha256(args.csv.read_bytes()).hexdigest()
    version = 'xeducation-logreg-v1-' + digest[:12]
    report = {
        'model_version': version, 'algorithm': 'LogisticRegression', 'source': 'https://www.kaggle.com/datasets/lakshmikalyan/lead-scoring-x-online-education',
        'dataset_sha256': digest, 'training_rows': len(X_train), 'test_rows': len(X_test), 'random_state': 42,
        'features': features, 'roc_auc': roc_auc_score(y_test, probabilities), 'average_precision': average_precision_score(y_test, probabilities),
        'brier_score': brier_score_loss(y_test, probabilities), 'accuracy_at_0_5': accuracy_score(y_test, probabilities >= 0.5),
        'confusion_matrix_at_0_5': confusion_matrix(y_test, probabilities >= 0.5).tolist(),
        'is_demo': True, 'limitations': ['Education-domain data; not validated on digital-service leads.', 'Random holdout, not temporal validation: dataset has no usable event timestamp.', 'Only source and website engagement features used; budgets, services and previous enquiries are not invented.', 'Dataset capture timing is not proven: prospective leakage must be reassessed on real deployment data.', 'HIGH/MEDIUM/LOW thresholds are configurable demonstration defaults, not business-approved calibration.'],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    joblib.dump({'pipeline': pipeline, 'version': version, 'is_demo': True}, args.output / 'lead_model.joblib')
    (args.output / 'metrics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
