"""TfL live arrivals. Upstream failures never become an empty success response."""

from datetime import UTC, datetime
from urllib.parse import quote

import httpx
from pydantic import AwareDatetime, BaseModel, Field

from app.schemas import LiveArrival, LiveResponse, Route

TFL_BASE_URL = "https://api.tfl.gov.uk"


class TflUnavailable(Exception):
    """A request or its response could not provide trustworthy arrivals."""


class _Prediction(BaseModel):
    vehicle_id: str = Field(alias="vehicleId", min_length=1)
    line_id: str = Field(alias="lineId", min_length=1)
    naptan_id: str = Field(alias="naptanId", min_length=1)
    direction: str | None = None
    destination_name: str | None = Field(default=None, alias="destinationName")
    time_to_station_s: int = Field(alias="timeToStation", ge=0, strict=True)
    expected_arrival: AwareDatetime = Field(alias="expectedArrival")


def get_live(
    route: Route,
    *,
    app_key: str,
    direction: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> LiveResponse:
    if not app_key or app_key == "your-tfl-app-key" or route.line_id == "fixture":
        raise TflUnavailable
    if route.mode == "tube" and not direction:
        # Tube stations serve both directions; do not mix their platforms.
        raise TflUnavailable

    params = {"app_key": app_key}
    if direction:
        params["direction"] = direction
    path = (
        f"/Line/{quote(route.line_id, safe='')}/Arrivals/"
        f"{quote(route.origin.naptan_id, safe='')}"
    )
    try:
        with httpx.Client(
            base_url=TFL_BASE_URL, timeout=3.0, transport=transport
        ) as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, list):
            raise TypeError("Expected a list of predictions")

        arrivals = []
        for item in payload:
            if not isinstance(item, dict):
                raise TypeError("Expected a prediction object")
            prediction = _Prediction.model_validate(item)
            # Defend against unrelated stops/lines even on the filtered endpoint.
            if (
                prediction.line_id != route.line_id
                or prediction.naptan_id != route.origin.naptan_id
                or (direction and prediction.direction not in (None, "", direction))
            ):
                continue
            arrivals.append(
                LiveArrival(
                    **prediction.model_dump(
                        exclude={"expected_arrival", "naptan_id", "direction"}
                    ),
                    expected_arrival=prediction.expected_arrival.astimezone(UTC),
                )
            )
    except (httpx.HTTPError, ValueError, TypeError):
        # Do not forward exception text: request URLs can contain the API key.
        raise TflUnavailable from None

    arrivals.sort(key=lambda arrival: arrival.expected_arrival)
    return LiveResponse(
        route_id=route.route_id, arrivals=arrivals, fetched_at=datetime.now(UTC)
    )
