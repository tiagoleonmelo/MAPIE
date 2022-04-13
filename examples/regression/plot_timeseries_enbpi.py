"""
==================================================================
Estimating prediction intervals of time series forecast with EnbPI
==================================================================
This example uses
:class:`mapie.time_series_regression.MapieTimeSeriesRegressor` to estimate
prediction intervals associated with time series forecast. It follows [6] and
an alternative expermimental implemetation inspired from [2]

We use here the Victoria electricity demand dataset used in the book
"Forecasting: Principles and Practice" by R. J. Hyndman and G. Athanasopoulos.
The electricity demand features daily and weekly seasonalities and is impacted
by the temperature, considered here as a exogeneous variable.

A Random Forest model is aloready fitted on data. The hyper-parameters are
optimized with a :class:`sklearn.model_selection.RandomizedSearchCV` using a
sequential :class:`sklearn.model_selection.TimeSeriesSplit` cross validation,
in which the training set is prior to the validation set.
The best model is then feeded into
:class:`mapie.time_series_regression.MapieTimeSeriesRegressor` to estimate the
associated prediction intervals. We compare four approaches: with or without
``partial_fit`` called at every step, and following [6] or a approach inspired
from [2]. It appears that the approach inspired from [2] and ``partial_fit``
offer higher coverage, but with higher width of PIs and are much slower.
"""
import warnings

import numpy as np
import pandas as pd
from matplotlib import pylab as plt
from sklearn.ensemble import RandomForestRegressor

from mapie.metrics import regression_coverage_score
from mapie.subsample import BlockBootstrap
from mapie.time_series_regression import MapieTimeSeriesRegressor

warnings.simplefilter("ignore")

# Load input data and feature engineering
demand_df = pd.read_csv(
    "../data/demand_temperature.csv", parse_dates=True, index_col=0
)

demand_df["Date"] = pd.to_datetime(demand_df.index)
demand_df["Weekofyear"] = demand_df.Date.dt.isocalendar().week.astype("int64")
demand_df["Weekday"] = demand_df.Date.dt.isocalendar().day.astype("int64")
demand_df["Hour"] = demand_df.index.hour
n_lags = 5
for hour in range(1, n_lags):
    demand_df[f"Lag_{hour}"] = demand_df["Demand"].shift(hour)

# Train/validation/test split
num_test_steps = 24 * 7
demand_train = demand_df.iloc[:-num_test_steps, :].copy()
demand_test = demand_df.iloc[-num_test_steps:, :].copy()
features = ["Weekofyear", "Weekday", "Hour", "Temperature"] + [
    f"Lag_{hour}" for hour in range(1, n_lags)
]

X_train = demand_train.loc[
    ~np.any(demand_train[features].isnull(), axis=1), features
]
y_train = demand_train.loc[X_train.index, "Demand"]
X_test = demand_test.loc[:, features]
y_test = demand_test["Demand"]

# Model: Random Forest previously optimized with a cross-validation
model = RandomForestRegressor(max_depth=10, n_estimators=50, random_state=59)

# Estimate prediction intervals on test set with best estimator
alpha = 0.05
cv_MapieTimeSeries = BlockBootstrap(
    n_resamplings=100, length=48, overlapping=True, random_state=59
)

mapie_plus = MapieTimeSeriesRegressor(
    model, method="plus", cv=cv_MapieTimeSeries, agg_function="mean", n_jobs=-1
)
mapie_enpbi = MapieTimeSeriesRegressor(
    model, method="plus", cv=cv_MapieTimeSeries, agg_function="mean", n_jobs=-1
)

gap = 1

print("EnbPI, with no partial_fit, width optimization")
mapie_enpbi = mapie_enpbi.fit(X_train, y_train)
y_pred_npfit_enbpi, y_pis_npfit_enbpi = mapie_enpbi.predict(
    X_test, alpha=alpha, ensemble=True, beta_optimize=True
)
coverage_npfit_enbpi = regression_coverage_score(
    y_test, y_pis_npfit_enbpi[:, 0, 0], y_pis_npfit_enbpi[:, 1, 0]
)
width_npfit_enbpi = (
    y_pis_npfit_enbpi[:, 1, 0] - y_pis_npfit_enbpi[:, 0, 0]
).mean()

print("EnbPI with partial_fit, width optimization")
mapie_enpbi = mapie_enpbi.fit(X_train, y_train)
y_pred_pfit_enbpi = np.zeros(y_pred_npfit_enbpi.shape)
y_pis_pfit_enbpi = np.zeros(y_pis_npfit_enbpi.shape)

y_pred_pfit_enbpi[:gap], y_pis_pfit_enbpi[:gap, :, :] = mapie_enpbi.predict(
    X_test.iloc[:gap, :], alpha=alpha, ensemble=True, beta_optimize=True
)

for step in range(gap, len(X_test), gap):
    mapie_enpbi.partial_fit(
        X_test.iloc[(step - gap) : step, :],
        y_test.iloc[(step - gap) : step],
    )
    (
        y_pred_pfit_enbpi[step : step + gap],
        y_pis_pfit_enbpi[step : step + gap, :, :],
    ) = mapie_enpbi.predict(
        X_test.iloc[step : (step + gap), :],
        alpha=alpha,
        ensemble=True,
        beta_optimize=True,
    )
coverage_pfit_enbpi = regression_coverage_score(
    y_test, y_pis_pfit_enbpi[:, 0, 0], y_pis_pfit_enbpi[:, 1, 0]
)
width_pfit_enbpi = (
    y_pis_pfit_enbpi[:, 1, 0] - y_pis_pfit_enbpi[:, 0, 0]
).mean()

print("EnbPI with partial_fit, NO width optimization")
mapie_enpbi = mapie_enpbi.fit(X_train, y_train)
y_pred_pfit_enbpi_no_opt = np.zeros(y_pred_npfit_enbpi.shape)
y_pis_pfit_enbpi_no_opt = np.zeros(y_pis_npfit_enbpi.shape)
(
    y_pred_pfit_enbpi_no_opt[:gap],
    y_pis_pfit_enbpi_no_opt[:gap, :, :],
) = mapie_enpbi.predict(
    X_test.iloc[:gap, :], alpha=alpha, ensemble=True, beta_optimize=False
)

for step in range(gap, len(X_test), gap):
    mapie_enpbi.partial_fit(
        X_test.iloc[(step - gap) : step, :],
        y_test.iloc[(step - gap) : step],
    )
    (
        y_pred_pfit_enbpi_no_opt[step : step + gap],
        y_pis_pfit_enbpi_no_opt[step : step + gap, :, :],
    ) = mapie_enpbi.predict(
        X_test.iloc[step : (step + gap), :],
        alpha=alpha,
        ensemble=True,
        beta_optimize=False,
    )
coverage_pfit_enbpi_no_opt = regression_coverage_score(
    y_test, y_pis_pfit_enbpi_no_opt[:, 0, 0], y_pis_pfit_enbpi_no_opt[:, 1, 0]
)
width_pfit_enbpi_no_opt = (
    y_pis_pfit_enbpi_no_opt[:, 1, 0] - y_pis_pfit_enbpi_no_opt[:, 0, 0]
).mean()


print("Plus, with partial_fit, width optimization")
mapie_plus = mapie_plus.fit(X_train, y_train)
y_pred_pfit_plus = np.zeros(y_pred_npfit_enbpi.shape)
y_pis_pfit_plus = np.zeros(y_pis_npfit_enbpi.shape)
(y_pred_pfit_plus[:gap], y_pis_pfit_plus[:gap, :, :],) = mapie_plus.predict(
    X_test.iloc[:gap, :],
    alpha=alpha,
    beta_optimize=True,
)
for step in range(gap, len(X_test), gap):
    mapie_plus.partial_fit(
        X_test.iloc[(step - gap) : step, :],
        y_test.iloc[(step - gap) : step],
    )
    (
        y_pred_pfit_plus[step : step + gap],
        y_pis_pfit_plus[step : step + gap, :, :],
    ) = mapie_plus.predict(
        X_test.iloc[step : (step + gap), :],
        alpha=alpha,
        ensemble=True,
        beta_optimize=True,
    )

coverage_pfit_plus = regression_coverage_score(
    y_test, y_pis_pfit_plus[:, 0, 0], y_pis_pfit_plus[:, 1, 0]
)
width_pfit_plus = (y_pis_pfit_plus[:, 1, 0] - y_pis_pfit_plus[:, 0, 0]).mean()

print("Plus, with partial_fit, NO width optimization")
mapie_plus = mapie_plus.fit(X_train, y_train)
y_pred_pfit_plus_no_opt = np.zeros(y_pred_npfit_enbpi.shape)
y_pis_pfit_plus_no_opt = np.zeros(y_pis_npfit_enbpi.shape)
(
    y_pred_pfit_plus_no_opt[:gap],
    y_pis_pfit_plus_no_opt[:gap, :, :],
) = mapie_plus.predict(
    X_test.iloc[:gap, :],
    alpha=alpha,
    beta_optimize=False,
)
for step in range(gap, len(X_test), gap):
    mapie_plus.partial_fit(
        X_test.iloc[(step - gap) : step, :],
        y_test.iloc[(step - gap) : step],
    )
    (
        y_pred_pfit_plus_no_opt[step : step + gap],
        y_pis_pfit_plus_no_opt[step : step + gap, :, :],
    ) = mapie_plus.predict(
        X_test.iloc[step : (step + gap), :],
        alpha=alpha,
        ensemble=True,
        beta_optimize=False,
    )

coverage_pfit_plus_no_opt = regression_coverage_score(
    y_test, y_pis_pfit_plus_no_opt[:, 0, 0], y_pis_pfit_plus_no_opt[:, 1, 0]
)
width_pfit_plus_no_opt = (
    y_pis_pfit_plus_no_opt[:, 1, 0] - y_pis_pfit_plus_no_opt[:, 0, 0]
).mean()

print("Plus, with partial_fit, MapieRegressor_Like")
mapie_plus = mapie_plus.fit(X_train, y_train)
y_pred_pfit_MR = np.zeros(y_pred_npfit_enbpi.shape)
y_pis_pfit_MR = np.zeros(y_pis_npfit_enbpi.shape)
y_pred_pfit_MR[:gap], y_pis_pfit_MR[:gap, :, :] = mapie_plus.root_predict(
    X_test.iloc[:gap, :], alpha=alpha
)
for step in range(gap, len(X_test), gap):
    mapie_plus.partial_fit(
        X_test.iloc[(step - gap) : step, :],
        y_test.iloc[(step - gap) : step],
    )
    (
        y_pred_pfit_MR[step : step + gap],
        y_pis_pfit_MR[step : step + gap, :, :],
    ) = mapie_plus.root_predict(
        X_test.iloc[step : (step + gap), :],
        alpha=alpha,
        ensemble=True,
    )

coverage_pfit_MR = regression_coverage_score(
    y_test, y_pis_pfit_MR[:, 0, 0], y_pis_pfit_MR[:, 1, 0]
)
width_pfit_MR = (y_pis_pfit_MR[:, 1, 0] - y_pis_pfit_MR[:, 0, 0]).mean()

# Print results
print(
    "Coverage / prediction interval width mean for MapieTimeSeriesRegressor: "
    "\nEnbPI without any partial_fit:"
    f"{coverage_npfit_enbpi :.3f}, {width_npfit_enbpi:.3f}"
)
print(
    "Coverage / prediction interval width mean for MapieTimeSeriesRegressor: "
    "\nEnbPI with partial_fit:"
    f"{coverage_pfit_enbpi:.3f}, {width_pfit_enbpi:.3f}"
)
print(
    "Coverage / prediction interval width mean for MapieTimeSeriesRegressor: "
    "\nEnbPI with partial_fit, no with optimization:"
    f"{coverage_pfit_enbpi_no_opt:.3f}, {width_pfit_enbpi_no_opt:.3f}"
)
print(
    "Coverage / prediction interval width mean for MapieTimeSeriesRegressor: "
    "\nPlus, with partial_fit:"
    f"{coverage_pfit_plus:.3f}, {width_pfit_plus:.3f}"
)
print(
    "Coverage / prediction interval width mean for MapieTimeSeriesRegressor: "
    "\nPlus, with partial_fit. no width optimization:"
    f"{coverage_pfit_plus_no_opt:.3f}, {width_pfit_plus_no_opt:.3f}"
)
print(
    "Coverage / prediction interval width mean for MapieTimeSeriesRegressor: "
    "\nMR_Like, with partial_fit:"
    f"{coverage_pfit_MR:.3f}, {width_pfit_MR:.3f}"
)

# Plot estimated prediction intervals on test set
fig, ((ax1, ax2, ax3), (ax4, ax5, ax6)) = plt.subplots(
    nrows=2, ncols=3, figsize=(30, 25), sharey="row", sharex="col"
)

for ax in [ax1, ax2, ax3, ax4, ax5, ax6]:
    ax.set_ylabel("Hourly demand (GW)")
    ax.plot(demand_test.Demand, lw=2, label="Test data", c="C1")


ax1.plot(
    demand_test.index, y_pred_npfit_enbpi, lw=2, c="C2", label="Predictions"
)
ax1.fill_between(
    demand_test.index,
    y_pis_npfit_enbpi[:, 0, 0],
    y_pis_npfit_enbpi[:, 1, 0],
    color="C2",
    alpha=0.2,
    label="MapieTimeSeriesRegressor PIs",
)
ax1.set_title(
    "EnbPI, without partial_fit.\n"
    f"Coverage:{coverage_npfit_enbpi:.3f}  Width:{width_npfit_enbpi:.3f}"
)

ax2.plot(
    demand_test.index, y_pred_pfit_enbpi, lw=2, c="C2", label="Predictions"
)
ax2.fill_between(
    demand_test.index,
    y_pis_pfit_enbpi[:, 0, 0],
    y_pis_pfit_enbpi[:, 1, 0],
    color="C2",
    alpha=0.2,
    label="MapieTimeSeriesRegressor PIs",
)
ax2.set_title(
    "EnbPI with partial_fit.\n"
    f"Coverage:{coverage_pfit_enbpi:.3f}  Width:{width_pfit_enbpi:.3f}"
)

ax3.plot(
    demand_test.index,
    y_pred_pfit_enbpi_no_opt,
    lw=2,
    c="C2",
    label="Predictions",
)
ax3.fill_between(
    demand_test.index,
    y_pis_pfit_enbpi_no_opt[:, 0, 0],
    y_pis_pfit_enbpi_no_opt[:, 1, 0],
    color="C2",
    alpha=0.2,
    label="MapieTimeSeriesRegressor PIs",
)
ax3.set_title(
    "EnbPI with partial_fit. No width optimization\n"
    f"Coverage:{coverage_pfit_enbpi_no_opt:.3f}"
    f"Width:{width_pfit_enbpi_no_opt:.3f}"
)

ax4.plot(
    demand_test.index,
    y_pred_pfit_plus,
    lw=2,
    c="C2",
    label="Predictions",
)
ax4.fill_between(
    demand_test.index,
    y_pis_pfit_plus[:, 0, 0],
    y_pis_pfit_plus[:, 1, 0],
    color="C2",
    alpha=0.2,
    label="MapieTimeSeriesRegressor PIs",
)
ax4.set_title(
    "Plus, with partial_fit.\n"
    f"Coverage:{coverage_pfit_plus:.3f}"
    f"Width:{width_pfit_plus:.3f}"
)

ax5.plot(
    demand_test.index,
    y_pred_pfit_plus_no_opt,
    lw=2,
    c="C2",
    label="Predictions",
)
ax5.fill_between(
    demand_test.index,
    y_pis_pfit_plus_no_opt[:, 0, 0],
    y_pis_pfit_plus_no_opt[:, 1, 0],
    color="C2",
    alpha=0.2,
    label="MapieTimeSeriesRegressor PIs",
)
ax5.set_title(
    "Plus, with partial_fit no width optimization\n"
    f"Coverage:{coverage_pfit_plus_no_opt:.3f}"
    f"Width:{width_pfit_plus_no_opt:.3f}"
)


ax6.plot(demand_test.index, y_pred_pfit_MR, lw=2, c="C2", label="Predictions")
ax6.fill_between(
    demand_test.index,
    y_pis_pfit_MR[:, 0, 0],
    y_pis_pfit_MR[:, 1, 0],
    color="C2",
    alpha=0.2,
    label="MapieTimeSeriesRegressor PIs",
)
ax6.set_title(
    "MapieRegressor Like, with partial_fit\n"
    f"Coverage:{coverage_pfit_MR:.3f}  Width:{width_pfit_MR:.3f}"
)
ax1.legend()
plt.show()
