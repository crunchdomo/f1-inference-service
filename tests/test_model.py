"""Quality gate: the model's ranking quality (ROC-AUC) must stay above a threshold.
This is the check a CI/CD pipeline would gate a deploy on."""

from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from app.train import (CATEGORICAL, NUMERIC, add_dnf_feature, build_pipeline,
                       circuit_dnf_lookup, load_data)


def test_auc_above_threshold():
    df = load_data()
    train_df, test_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df["podium"]
    )

    lookup, fallback = circuit_dnf_lookup(train_df)
    train_df = add_dnf_feature(train_df, lookup, fallback)
    test_df = add_dnf_feature(test_df, lookup, fallback)

    cols = NUMERIC + CATEGORICAL
    model = build_pipeline()
    model.fit(train_df[cols], train_df["podium"])

    proba = model.predict_proba(test_df[cols])[:, 1]
    auc = roc_auc_score(test_df["podium"], proba)
    assert auc > 0.85
