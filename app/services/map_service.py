from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.schemas.models import TransportMode


@dataclass
class MapRouteResult:
    travel_minutes: int
    transfer_count: int
    route_summary: str
    route_steps: List[str]
    provider: str = "mock"


@dataclass
class LocationContext:
    normalized_address: str
    longitude: str
    latitude: str
    province: str
    city: str
    district: str
    formatted_address: str

    @property
    def location(self) -> Tuple[str, str]:
        return self.longitude, self.latitude


@dataclass
class NearbyHospital:
    poi_id: str
    name: str
    address: str
    city: str
    district: str
    province: str
    distance_meters: int
    type: str
    keytag: str
    tel: str
    longitude: str
    latitude: str


class MapService:
    def __init__(self) -> None:
        self._geocode_cache: Dict[str, LocationContext] = {}
        self._route_cache: Dict[Tuple[str, str, str], MapRouteResult] = {}
        self._nearby_hospital_cache: Dict[Tuple[str, str, int, int], List[NearbyHospital]] = {}

    def plan_route(
        self,
        origin: str,
        destination: str,
        transport_mode: TransportMode,
        fallback_profile: Dict,
        nearby_regions: List[str],
    ) -> MapRouteResult:
        cache_key = (origin.strip(), destination.strip(), transport_mode.value)
        cached_route = self._route_cache.get(cache_key)
        if cached_route is not None:
            return cached_route

        map_enabled = settings.map_provider == "amap" and bool(settings.amap_api_key)

        if settings.map_provider != "amap" or not settings.amap_api_key:
            route = self._fallback(origin, transport_mode, fallback_profile, nearby_regions)
            self._route_cache[cache_key] = route
            return route

        try:
            origin_context = self.resolve_location(origin)
            destination_context = self.resolve_location(destination)
            if origin_context is None or destination_context is None:
                route = self._fallback(origin, transport_mode, fallback_profile, nearby_regions)
                return route
            if not origin_context.longitude or not destination_context.longitude:
                route = self._fallback(origin, transport_mode, fallback_profile, nearby_regions)
                return route

            if transport_mode in {TransportMode.bus, TransportMode.metro}:
                route = self._plan_amap_transit(origin_context, destination_context, destination)
            elif transport_mode == TransportMode.walking:
                route = self._plan_amap_walking(origin_context.location, destination_context.location)
            else:
                route = self._plan_amap_driving(origin_context.location, destination_context.location)

            final_route = route or self._fallback(origin, transport_mode, fallback_profile, nearby_regions)
            if not map_enabled or final_route.provider != "mock":
                self._route_cache[cache_key] = final_route
            return final_route
        except Exception:
            route = self._fallback(origin, transport_mode, fallback_profile, nearby_regions)
            return route

    def resolve_location(self, address: str) -> Optional[LocationContext]:
        normalized = self._normalize_address(address)
        if normalized in self._geocode_cache:
            return self._geocode_cache[normalized]

        params = {
            "key": settings.amap_api_key,
            "address": normalized,
        }
        city_hint = self._extract_city_hint(address)
        if city_hint:
            params["city"] = city_hint

        try:
            response = self._get("/v3/geocode/geo", params)
            geocodes = response.get("geocodes") or []
            if not geocodes:
                context = self._infer_location_context(normalized)
            else:
                geocode = geocodes[0]
                location = geocode.get("location", "")
                if "," not in location:
                    context = self._infer_location_context(normalized)
                else:
                    lng, lat = location.split(",", 1)
                    city = self._resolve_city_name(geocode)
                    context = LocationContext(
                        normalized_address=normalized,
                        longitude=lng,
                        latitude=lat,
                        province=str(geocode.get("province") or ""),
                        city=city,
                        district=str(geocode.get("district") or ""),
                        formatted_address=str(geocode.get("formatted_address") or normalized),
                    )
        except Exception:
            context = self._infer_location_context(normalized)

        self._geocode_cache[normalized] = context
        return context

    def search_nearby_hospitals(
        self,
        origin: str,
        department: str,
        radius_meters: int = 8000,
        limit: int = 12,
    ) -> List[NearbyHospital]:
        cache_key = (origin.strip(), department, radius_meters, limit)
        cached = self._nearby_hospital_cache.get(cache_key)
        if cached is not None:
            return cached

        if settings.map_provider != "amap" or not settings.amap_api_key:
            return []

        origin_context = self.resolve_location(origin)
        if origin_context is None or not origin_context.longitude:
            return []

        queries = ["医院", f"{department} 医院"]
        deduped: Dict[str, NearbyHospital] = {}
        page_size = min(max(limit, 20), 25)

        for query in queries:
            for page in range(1, max(1, settings.nearby_search_pages) + 1):
                try:
                    response = self._get(
                        "/v3/place/around",
                        {
                            "key": settings.amap_api_key,
                            "location": self._join_location(origin_context.location),
                            "keywords": query,
                            "radius": radius_meters,
                            "sortrule": "distance",
                            "offset": page_size,
                            "page": page,
                        },
                    )
                except Exception:
                    break

                pois = response.get("pois") or []
                if not pois:
                    break

                for poi in pois:
                    parsed = self._parse_nearby_hospital(poi, origin_context.city)
                    if parsed is None:
                        continue
                    existing = deduped.get(parsed.poi_id)
                    if existing is None or parsed.distance_meters < existing.distance_meters:
                        deduped[parsed.poi_id] = parsed

                if len(pois) < page_size:
                    break

        hospitals = sorted(deduped.values(), key=lambda item: item.distance_meters)[:limit]
        self._nearby_hospital_cache[cache_key] = hospitals
        return hospitals

    def _plan_amap_walking(
        self, origin: Tuple[str, str], destination: Tuple[str, str]
    ) -> Optional[MapRouteResult]:
        response = self._get(
            "/v3/direction/walking",
            {
                "key": settings.amap_api_key,
                "origin": self._join_location(origin),
                "destination": self._join_location(destination),
            },
        )
        paths = ((response.get("route") or {}).get("paths") or [])
        if not paths:
            return None
        best_path = paths[0]
        travel_minutes = self._seconds_to_minutes(best_path.get("duration"))
        instructions = [
            step.get("instruction", "")
            for step in (best_path.get("steps") or [])
            if step.get("instruction")
        ]
        summary = "；".join(instructions[:3]) or "步行前往医院。"
        return MapRouteResult(
            travel_minutes=travel_minutes,
            transfer_count=0,
            route_summary=summary,
            route_steps=instructions[:3] if instructions else ["从当前位置步行前往医院。"],
            provider="高德地图",
        )

    def _plan_amap_driving(
        self, origin: Tuple[str, str], destination: Tuple[str, str]
    ) -> Optional[MapRouteResult]:
        response = self._get(
            "/v3/direction/driving",
            {
                "key": settings.amap_api_key,
                "origin": self._join_location(origin),
                "destination": self._join_location(destination),
                "strategy": 0,
            },
        )
        paths = ((response.get("route") or {}).get("paths") or [])
        if not paths:
            return None
        best_path = paths[0]
        travel_minutes = self._seconds_to_minutes(best_path.get("duration"))
        distance = best_path.get("distance", "0")
        instructions = [
            step.get("instruction", "")
            for step in (best_path.get("steps") or [])
            if step.get("instruction")
        ]
        summary = "；".join(instructions[:2]) or f"驾车约 {travel_minutes} 分钟，全程 {distance} 米。"
        return MapRouteResult(
            travel_minutes=travel_minutes,
            transfer_count=0,
            route_summary=summary,
            route_steps=instructions[:3] if instructions else [f"驾车前往医院，全程约 {distance} 米。"],
            provider="高德地图",
        )

    def _plan_amap_transit(
        self, origin: LocationContext, destination: LocationContext, destination_label: str
    ) -> Optional[MapRouteResult]:
        city_name = origin.city or destination.city or settings.default_city
        response = self._get(
            "/v3/direction/transit/integrated",
            {
                "key": settings.amap_api_key,
                "origin": self._join_location(origin.location),
                "destination": self._join_location(destination.location),
                "city": city_name,
                "strategy": 0,
                "nightflag": 0,
            },
        )
        transits = ((response.get("route") or {}).get("transits") or [])
        if not transits:
            return None

        best_transit = transits[0]
        travel_minutes = self._seconds_to_minutes(best_transit.get("duration"))
        segments = best_transit.get("segments") or []
        line_names = self._extract_transit_line_names(segments)
        transfer_count = max(0, len(line_names) - 1)
        route_steps = self._extract_transit_steps(segments, self._extract_destination_label(destination_label, destination))
        if line_names:
            summary = self._build_transit_summary(line_names, route_steps)
        else:
            summary = "先前往最近站点，再乘公交或地铁到医院附近，最后步行到院。"

        return MapRouteResult(
            travel_minutes=travel_minutes,
            transfer_count=transfer_count,
            route_summary=summary,
            route_steps=route_steps or ["先前往最近站点，再乘公交或地铁到医院附近。", "出站后步行至医院门口。"],
            provider="高德地图",
        )

    def _fallback(
        self,
        origin: str,
        transport_mode: TransportMode,
        fallback_profile: Dict,
        nearby_regions: List[str],
    ) -> MapRouteResult:
        base_minutes = int(fallback_profile.get("base_minutes", 30))
        if any(region in origin for region in nearby_regions):
            travel_minutes = max(12, base_minutes - 7)
        elif settings.default_city in origin:
            travel_minutes = base_minutes
        else:
            travel_minutes = base_minutes + 10

        return MapRouteResult(
            travel_minutes=travel_minutes,
            transfer_count=int(fallback_profile.get("transfers", 0)),
            route_summary=fallback_profile.get("route", "路线信息待补充"),
            route_steps=self._fallback_steps(transport_mode, travel_minutes, int(fallback_profile.get("transfers", 0))),
            provider="mock",
        )

    def _extract_transit_steps(self, segments: List[Dict], destination_label: str) -> List[str]:
        steps: List[str] = []
        pending_exit_name = ""
        last_arrival_name = ""
        for index, segment in enumerate(segments):
            walking = segment.get("walking") or {}
            walking_steps = walking.get("steps") or []
            bus = segment.get("bus") or {}
            buslines = bus.get("buslines") or []
            segment_exit_name = ((segment.get("exit") or {}).get("name") or "").strip()
            if buslines:
                departure_name = ((buslines[0].get("departure_stop") or {}).get("name") or "").strip()
                walking_distance = self._safe_int(walking.get("distance"), default=0)
                if index == 0 and departure_name and walking_distance > 0:
                    steps.append(f"先步行约 {walking_distance} 米，到 {departure_name} 站进站。")

            for line in buslines:
                line_name = (line.get("name") or "").split("(")[0].strip()
                departure = ((line.get("departure_stop") or {}).get("name") or "").strip()
                arrival = ((line.get("arrival_stop") or {}).get("name") or "").strip()
                via_num = self._safe_int(line.get("via_num"), default=0)
                via_text = f"，途经 {via_num} 站" if via_num > 0 else ""
                if line_name and departure and arrival:
                    steps.append(f"乘坐 {line_name}，从 {departure} 站上车，到 {arrival} 站下车{via_text}。")
                elif line_name:
                    steps.append(f"乘坐 {line_name} 前往医院方向。")
                if arrival:
                    last_arrival_name = arrival
                if segment_exit_name:
                    pending_exit_name = f"{arrival}站{segment_exit_name}" if arrival else segment_exit_name

            if not buslines and walking_steps:
                walking_distance = self._safe_int(walking.get("distance"), default=0)
                assistant_action = next(
                    (
                        step.get("assistant_action", "").strip()
                        for step in reversed(walking_steps)
                        if step.get("assistant_action")
                    ),
                    "",
                )
                destination_text = (
                    assistant_action.removeprefix("到达").strip()
                    if assistant_action.startswith("到达")
                    else destination_label
                )
                current_exit_name = pending_exit_name
                if not current_exit_name and segment_exit_name and last_arrival_name:
                    current_exit_name = f"{last_arrival_name}站{segment_exit_name}"
                if current_exit_name:
                    steps.append(f"从 {current_exit_name} 出站后步行约 {walking_distance} 米，到达 {destination_text}。")
                    pending_exit_name = ""
                elif walking_distance > 0:
                    steps.append(f"下车后步行约 {walking_distance} 米，到达 {destination_text}。")

        cleaned: List[str] = []
        for step in steps:
            if step and step not in cleaned:
                cleaned.append(step)
        return cleaned[:4]

    @staticmethod
    def _build_transit_summary(line_names: List[str], route_steps: List[str]) -> str:
        if len(route_steps) >= 2:
            return f"{route_steps[0].rstrip('。')}；{route_steps[1]}"
        if route_steps:
            return route_steps[0]
        if len(line_names) == 1:
            return f"先前往站点，乘坐 {line_names[0]}，下车后步行到医院。"
        if len(line_names) >= 2:
            return f"先前往站点，乘坐 {line_names[0]}，再换乘 {line_names[1]}，随后步行到医院。"
        return "先前往最近站点，再乘公交或地铁到医院附近。"

    @staticmethod
    def _extract_destination_label(raw_destination: str, destination_context: LocationContext) -> str:
        text = (raw_destination or "").strip() or destination_context.formatted_address or destination_context.normalized_address
        if "医院" in text:
            for marker in ("区", "县", "市"):
                if marker in text:
                    candidate = text.split(marker)[-1].strip()
                    if candidate and "医院" in candidate:
                        return candidate
            return text
        if destination_context.formatted_address:
            return destination_context.formatted_address
        return text or "医院"

    @staticmethod
    def _fallback_steps(
        transport_mode: TransportMode,
        travel_minutes: int,
        transfer_count: int,
    ) -> List[str]:
        if transport_mode == TransportMode.walking:
            return [
                "从当前位置直接步行前往医院。",
                f"全程预计约 {travel_minutes} 分钟，请根据体力决定是否步行。",
            ]
        if transport_mode in {TransportMode.bus, TransportMode.metro}:
            transfer_tip = "尽量选择少换乘路线。" if transfer_count > 0 else "优先选择直达站点。"
            vehicle = "地铁" if transport_mode == TransportMode.metro else "公交"
            return [
                f"先前往最近的{vehicle}站点。",
                f"乘坐{vehicle}前往医院附近站点，预计约 {travel_minutes} 分钟。",
                f"出站后步行到医院门口，{transfer_tip}",
            ]
        return [
            "建议直接打车前往医院门口。",
            f"车程预计约 {travel_minutes} 分钟。",
            "下车后按门诊指引进入大厅签到。",
        ]

    @staticmethod
    def _extract_transit_line_names(segments: List[Dict]) -> List[str]:
        line_names: List[str] = []
        for segment in segments:
            bus = segment.get("bus") or {}
            buslines = bus.get("buslines") or []
            for line in buslines:
                name = (line.get("name") or "").split("(")[0].strip()
                if name and name not in line_names:
                    line_names.append(name)
        return line_names

    @staticmethod
    def _normalize_address(address: str) -> str:
        cleaned = address.strip()
        if not cleaned:
            return settings.default_city
        if MapService._has_explicit_city_scope(cleaned):
            return cleaned
        return f"{settings.default_city}{cleaned}"

    @staticmethod
    def _has_explicit_city_scope(address: str) -> bool:
        markers = ("省", "市", "自治区", "自治州", "特别行政区")
        return any(marker in address for marker in markers)

    @staticmethod
    def _extract_city_hint(address: str) -> Optional[str]:
        cleaned = address.strip()
        if not cleaned:
            return settings.default_city
        if not MapService._has_explicit_city_scope(cleaned):
            return settings.default_city

        city_index = cleaned.find("市")
        if city_index > 0:
            province_index = cleaned.find("省")
            if province_index >= 0 and province_index < city_index:
                return cleaned[province_index + 1 : city_index + 1]

            autonomous_region_index = cleaned.find("自治区")
            if autonomous_region_index >= 0 and autonomous_region_index < city_index:
                return cleaned[autonomous_region_index + 3 : city_index + 1]

            return cleaned[: city_index + 1]
        return None

    @staticmethod
    def _resolve_city_name(geocode: Dict) -> str:
        city_value = geocode.get("city")
        if isinstance(city_value, list):
            city_value = next((item for item in city_value if item), "")
        city_name = str(city_value or "").strip()
        if city_name:
            return city_name

        province = str(geocode.get("province") or "").strip()
        if province.endswith("市"):
            return province
        return province

    @staticmethod
    def _parse_nearby_hospital(poi: Dict, expected_city: str) -> Optional[NearbyHospital]:
        name = str(poi.get("name") or "").strip()
        poi_type = str(poi.get("type") or "").strip()
        city = str(poi.get("cityname") or expected_city or "").strip()
        district = str(poi.get("adname") or "").strip()
        province = str(poi.get("pname") or "").strip()
        address = str(poi.get("address") or "").strip()
        location = str(poi.get("location") or "")

        if not name or "," not in location:
            return None
        if "医院" not in name and "医院" not in poi_type:
            return None
        if any(keyword in name for keyword in ("宠物", "美容", "康复理疗", "体检中心")):
            return None
        if "医院" in name and any(
            keyword in name
            for keyword in (
                "住院部",
                "病区",
                "实验室",
                "门诊",
                "诊室",
                "检验科",
                "服务站",
                "卫生所",
                "药房",
                "研究院",
                "住院处",
                "中药房",
            )
        ):
            return None
        if any(keyword in name for keyword in ("社区卫生服务", "卫生服务中心", "卫生服务站", "社区医院")):
            return None
        if any(keyword in poi_type for keyword in ("住宅区", "住宅小区", "商务住宅", "诊所", "药房")):
            return None
        if expected_city and city and city != expected_city:
            return None

        lng, lat = location.split(",", 1)
        return NearbyHospital(
            poi_id=str(poi.get("id") or name),
            name=name,
            address=f"{province}{city}{district}{address}" if address and city not in address else address or name,
            city=city,
            district=district,
            province=province,
            distance_meters=MapService._safe_int(poi.get("distance"), default=2500),
            type=poi_type,
            keytag=str(poi.get("keytag") or "").strip(),
            tel=str(poi.get("tel") or "").strip(),
            longitude=lng,
            latitude=lat,
        )

    @staticmethod
    def _infer_location_context(address: str) -> LocationContext:
        province = ""
        city = settings.default_city
        district = ""

        if "省" in address:
            province = address.split("省", 1)[0] + "省"
            remainder = address.split("省", 1)[1]
        else:
            remainder = address
            if address.startswith(("北京", "上海", "天津", "重庆")) and "市" in address:
                province = address.split("市", 1)[0] + "市"

        if "市" in remainder:
            city = remainder.split("市", 1)[0] + "市"
            district_source = remainder.split("市", 1)[1]
        else:
            district_source = remainder
            if province.endswith("市"):
                city = province

        if "区" in district_source:
            district = district_source.split("区", 1)[0] + "区"
        elif "县" in district_source:
            district = district_source.split("县", 1)[0] + "县"

        return LocationContext(
            normalized_address=address,
            longitude="",
            latitude="",
            province=province,
            city=city,
            district=district,
            formatted_address=address,
        )

    @staticmethod
    def _join_location(location: Tuple[str, str]) -> str:
        return f"{location[0]},{location[1]}"

    @staticmethod
    def _seconds_to_minutes(seconds_value) -> int:
        try:
            seconds = int(float(seconds_value))
        except (TypeError, ValueError):
            return 30
        return max(1, round(seconds / 60))

    @staticmethod
    def _safe_int(value, default: int) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _get(path: str, params: Dict) -> Dict:
        response = httpx.get(
            f"{settings.amap_base_url}{path}",
            params=params,
            timeout=10.0,
            trust_env=False,
        )
        response.raise_for_status()
        data = response.json()
        if str(data.get("status")) != "1":
            raise ValueError(data.get("info", "AMap API request failed"))
        return data
