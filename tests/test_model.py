"""Quality gate: the model's ranking quality (ROC-AUC) on a held-out future season
must stay above a threshold. This is the check a CI/CD pipeline would gate on."""

from sklearn.metrics import roc_auc_score

from app.train import (CATEGORICAL, NUMERIC, add_dnf_feature, add_form_features,
                       build_pipeline, circuit_dnf_lookup, load_data)


def test_auc_above_threshold():
    df = add_form_features(load_data())
    test_season = int(df["season"].max())
    train_df = df[df["season"] < test_season].copy()
    test_df = df[df["season"] == test_season].copy()

    lookup, fallback = circuit_dnf_lookup(train_df)
    train_df = add_dnf_feature(train_df, lookup, fallback)
    test_df = add_dnf_feature(test_df, lookup, fallback)

    cols = NUMERIC + CATEGORICAL
    model = build_pipeline()
    model.fit(train_df[cols], train_df["podium"])

    proba = model.predict_proba(test_df[cols])[:, 1]
    auc = roc_auc_score(test_df["podium"], proba)
    assert auc > 0.85
