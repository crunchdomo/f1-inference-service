"""Quality gate: the model's held-out error must stay under a threshold.
This is the check a CI/CD pipeline would gate a deploy on."""

from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

from app.train import (CATEGORICAL, NUMERIC, add_dnf_feature, build_pipeline,
                       circuit_dnf_lookup, load_data)


def test_mae_under_threshold():
    df = load_data()
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)

    lookup, fallback = circuit_dnf_lookup(train_df)
    train_df = add_dnf_feature(train_df, lookup, fallback)
    test_df = add_dnf_feature(test_df, lookup, fallback)

    cols = NUMERIC + CATEGORICAL
    model = build_pipeline()
    model.fit(train_df[cols], train_df["position"])

    mae = mean_absolute_error(test_df["position"], model.predict(test_df[cols]))
    assert mae < 4.0
