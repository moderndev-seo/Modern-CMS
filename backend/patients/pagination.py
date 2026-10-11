"""Independent finite pages without changing all-record financial totals."""

from rest_framework.exceptions import ValidationError


def window(request, key, records, pages, label, size=100):
    parameter = f"{key}_page"
    try:
        page = int(request.query_params.get(parameter, 1))
        if page < 1 or page > 1000000:
            raise ValueError
    except (ValueError, TypeError):
        raise ValidationError(
            {parameter: "Use a positive page number up to 1000000."}
        ) from None
    count = len(records) if isinstance(records, (list, tuple)) else records.count()
    pages.append(
        {
            "parameter": parameter,
            "label": label,
            "page": page,
            "count": count,
            "size": size,
        }
    )
    return records[(page - 1) * size : page * size]
