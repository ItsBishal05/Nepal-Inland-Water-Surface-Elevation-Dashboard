import re
import numpy as np
import pandas as pd
from scipy.stats import linregress


def flag_outliers_iqr(data, colname):
    """
    Flag outliers in `data[colname]` using the 1.5×IQR rule.

    Returns a boolean Series aligned with `data.index`.
    Outliers are values < Q1 - 1.5*IQR or > Q3 + 1.5*IQR.
    """
    if data is None or data.empty or colname not in data.columns:
        return pd.Series(False, index=getattr(data, "index", []))

    vals = data[colname].dropna()
    if vals.empty:
        return pd.Series(False, index=data.index)

    Q1 = np.percentile(vals, 25)
    Q3 = np.percentile(vals, 75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR

    return (data[colname] < lower) | (data[colname] > upper)


def compute_trend(x, y):
    """
    Compute a linear trend via scipy.stats.linregress.

    `x` must be an iterable of date-like objects (uses .toordinal()).
    Returns the linregress result (has .slope, .intercept, .rvalue, .pvalue),
    or None if there are fewer than 2 points or the fit fails.
    """
    if x is None or y is None or len(x) < 2 or len(y) < 2:
        return None
    try:
        x_num = np.array([d.toordinal() for d in x])
        return linregress(x_num, y)
    except (AttributeError, TypeError, ValueError):
        return None


def clean_name(name):
    """
    Clean and standardize lake / feature names for fuzzy matching.

    Lowercases, strips punctuation and common prefixes, collapses whitespace.
    Note: currently unused in the lake + river dashboard, kept for future use
    (e.g. name-based search or shapefile-to-CSV matching).
    """
    if name is None:
        return ""
    name = str(name).lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name)

    prefixes = ['lake', 'pond', 'reservoir', 'waterbody', 'tal', 'pokhari']
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name.replace(prefix, '', 1).strip()

    return name.strip()