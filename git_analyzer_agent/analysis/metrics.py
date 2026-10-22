from statistics import mean, median


def percentile(
    values: list[float],
    percentile_value: float,
) -> float | None:
    """
    Calculate a percentile using linear interpolation.
    """
    if not values:
        return None

    sorted_values = sorted(values)

    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)

    position = (
        (len(sorted_values) - 1)
        * percentile_value
        / 100
    )

    lower_index = int(position)
    upper_index = lower_index + 1

    if upper_index >= len(sorted_values):
        return round(
            sorted_values[-1],
            2,
        )

    fraction = position - lower_index

    result = (
        sorted_values[lower_index]
        + fraction
        * (
            sorted_values[upper_index]
            - sorted_values[lower_index]
        )
    )

    return round(result, 2)


def calculate_distribution(
    values: list[float],
) -> dict:
    """
    Calculate average, median, P75 and P90.
    """
    if not values:
        return {
            "count": 0,
            "average": None,
            "median": None,
            "p75": None,
            "p90": None,
        }

    return {
        "count": len(values),
        "average": round(mean(values), 2),
        "median": round(median(values), 2),
        "p75": percentile(values, 75),
        "p90": percentile(values, 90),
    }


def extract_feature_metric(
    feature: dict,
    metric_name: str,
) -> float | None:
    """
    Extract a metric from a normalized feature lifecycle.
    """
    lifecycle = feature.get("lifecycle") or {}

    review = (
        lifecycle.get("review")
        or {}
    )

    stage_durations = (
        lifecycle.get("stage_durations")
        or {}
    )

    metric_paths = {
        "feature_development":
            stage_durations.get(
                "feature_development_hours"
            ),

        "pr_review":
            review.get(
                "average_time_to_first_review_hours"
            ),

        "merge_to_dev":
            stage_durations.get(
                "merge_to_dev_hours"
            ),

        "dev_to_test":
            stage_durations.get(
                "dev_to_test_hours"
            ),

        "test_to_prod":
            stage_durations.get(
                "test_to_prod_hours"
            ),

        "end_to_end":
            lifecycle.get(
                "end_to_end_hours"
            ),
    }

    return metric_paths.get(metric_name)


def calculate_repository_metrics(
    features: list[dict],
    exclude_incomplete: bool = True,
) -> dict:
    """
    Calculate repository-level lead-time metrics.

    Incomplete features are excluded by default.
    """
    completed_features = [
        feature
        for feature in features
        if (
            feature.get("lifecycle", {})
            .get("complete_lifecycle", False)
        )
    ]

    incomplete_features = [
        feature
        for feature in features
        if feature not in completed_features
    ]

    analysis_features = (
        completed_features
        if exclude_incomplete
        else features
    )

    metric_names = [
        "feature_development",
        "pr_review",
        "merge_to_dev",
        "dev_to_test",
        "test_to_prod",
        "end_to_end",
    ]

    metrics = {}

    for metric_name in metric_names:
        values = []

        for feature in analysis_features:
            value = extract_feature_metric(
                feature,
                metric_name,
            )

            if value is not None:
                values.append(value)

        metrics[metric_name] = (
            calculate_distribution(values)
        )

    return {
        "feature_count": len(analysis_features),

        "completed_feature_count": len(
            completed_features
        ),

        "incomplete_feature_count": len(
            incomplete_features
        ),

        "excluded_incomplete_features": (
            [
                feature.get("feature_name")
                or feature.get("branch")
                for feature
                in incomplete_features
            ]
            if exclude_incomplete
            else []
        ),

        "metrics": metrics,
    }


def build_feature_metric_summary(
    feature: dict,
) -> dict:
    """
    Build a normalized metric summary for one feature.
    """
    lifecycle = feature.get("lifecycle") or {}

    review = (
        lifecycle.get("review")
        or {}
    )

    stage_durations = (
        lifecycle.get("stage_durations")
        or {}
    )

    return {
        "feature_name":
            feature.get("feature_name"),

        "branch":
            feature.get("branch"),

        "complete":
            lifecycle.get(
                "complete_lifecycle",
                False,
            ),

        "feature_development_hours":
            stage_durations.get(
                "feature_development_hours"
            ),

        "pr_review_hours":
            review.get(
                "average_time_to_first_review_hours"
            ),

        "merge_to_dev_hours":
            stage_durations.get(
                "merge_to_dev_hours"
            ),

        "dev_to_test_hours":
            stage_durations.get(
                "dev_to_test_hours"
            ),

        "test_to_prod_hours":
            stage_durations.get(
                "test_to_prod_hours"
            ),

        "end_to_end_hours":
            lifecycle.get(
                "end_to_end_hours"
            ),
    }


def build_feature_metric_breakdown(
    features: list[dict],
) -> list[dict]:
    """
    Return normalized metrics for every feature.
    """
    return [
        build_feature_metric_summary(feature)
        for feature in features
    ]


def build_repository_metric_summary(
    features: list[dict],
) -> dict:
    """
    Build repository-wide metrics and feature breakdown.
    """
    repository_metrics = calculate_repository_metrics(
        features,
        exclude_incomplete=True,
    )

    return {
        "repository_metrics":
            repository_metrics,

        "feature_breakdown":
            build_feature_metric_breakdown(
                features
            ),
    }


def calculate_final_repository_analysis(
    analyzed_features: list[dict],
) -> dict:
    """
    Produce the final repository-level analysis.

    Only completed features are used for aggregate
    lead-time metrics.
    """
    completed_features = [
        feature
        for feature in analyzed_features
        if (
            feature.get("lifecycle", {})
            .get("complete_lifecycle", False)
        )
    ]

    incomplete_features = [
        feature
        for feature in analyzed_features
        if not (
            feature.get("lifecycle", {})
            .get("complete_lifecycle", False)
        )
    ]

    metrics = calculate_repository_metrics(
        analyzed_features,
        exclude_incomplete=True,
    )

    return {
        "total_features":
            len(analyzed_features),

        "completed_features":
            len(completed_features),

        "incomplete_features":
            len(incomplete_features),

        "metrics":
            metrics,

        "feature_breakdown":
            build_feature_metric_breakdown(
                analyzed_features
            ),

        "incomplete_feature_details": [
            {
                "feature_name":
                    feature.get(
                        "feature_name"
                    ),

                "branch":
                    feature.get("branch"),

                "completion_reason":
                    feature.get(
                        "completion_reason"
                    ),
            }
            for feature
            in incomplete_features
        ],
    }