from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from app.agents.base import BaseAgent
from app.core.config import settings
from app.schemas.models import HospitalCandidate, Preferences, ScoreBreakdown, TriageResult, TransportMode
from app.services.hospital_catalog import HospitalCatalog
from app.services.map_service import MapRouteResult, MapService, NearbyHospital
from app.services.priority_hospital_catalog import PriorityHospitalCatalog


class HospitalRecommendationAgent(BaseAgent):
    name = "HospitalRecommendationAgent"
    DEPARTMENT_HINTS = {
        "心内科": {"心", "心血管", "胸科"},
        "呼吸内科": {"呼吸", "肺", "胸科"},
        "神经内科": {"神经", "脑"},
        "消化内科": {"消化", "胃", "肠", "肝胆"},
        "骨科": {"骨", "创伤", "关节", "脊柱"},
        "内分泌科": {"内分泌", "糖尿病", "代谢"},
        "儿科": {"儿童", "儿科", "妇幼"},
        "妇科": {"妇幼", "妇产", "产科", "妇科"},
        "口腔科": {"口腔"},
        "皮肤科": {"皮肤"},
        "精神科": {"精神", "心理"},
        "肛肠科": {"肛肠"},
        "全科医学科": set(),
    }

    URGENT_PRIORITIES = {"soon", "urgent"}

    def __init__(
        self,
        catalog: HospitalCatalog,
        map_service: MapService,
        priority_catalog: PriorityHospitalCatalog,
    ) -> None:
        self.catalog = catalog
        self.map_service = map_service
        self.priority_catalog = priority_catalog

    def run(
        self,
        current_location: str,
        transport_mode: TransportMode,
        triage: TriageResult,
        preferences: Preferences,
    ) -> List[HospitalCandidate]:
        origin_context = self.map_service.resolve_location(current_location)
        current_city = self._normalize_city_name(origin_context.city if origin_context and origin_context.city else "")
        local_hospitals = self.catalog.list_hospitals()
        local_lookup = {
            self._normalize_hospital_name(hospital["name"]): hospital
            for hospital in local_hospitals
        }
        priority_hospitals = self.priority_catalog.list_by_city(current_city) if current_city else []

        live_hospitals = self.map_service.search_nearby_hospitals(
            origin=current_location,
            department=triage.department,
            radius_meters=settings.nearby_search_radius_meters,
            limit=settings.nearby_hospital_limit,
        )

        candidate_records: List[Dict] = []
        seen_names: set[str] = set()

        for nearby in live_hospitals:
            display_name = self._simplify_live_hospital_name(nearby.name)
            if not self._is_relevant_live_hospital(nearby.name, triage.department):
                continue
            normalized_name = self._normalize_hospital_name(display_name)
            if normalized_name in seen_names:
                continue
            matched_local = self._match_local_hospital(normalized_name, local_lookup)
            matched_priority = self.priority_catalog.match_by_name(current_city, display_name) if current_city else None
            record = self._build_live_record(
                nearby=nearby,
                triage=triage,
                matched_local=matched_local,
                matched_priority=matched_priority,
                display_name=display_name,
            )
            candidate_records.append(record)
            seen_names.add(normalized_name)

        if not candidate_records:
            candidate_records = self._fallback_local_records(
                current_location=current_location,
                triage=triage,
                local_hospitals=local_hospitals,
            )

        if not candidate_records:
            return []

        if current_city == "西安市" and triage.urgency in self.URGENT_PRIORITIES and priority_hospitals:
            priority_records = self._build_priority_records(priority_hospitals, triage)
            priority_candidates = self._score_priority_hospitals(
                candidate_records=priority_records,
                current_location=current_location,
                transport_mode=transport_mode,
                triage=triage,
                preferences=preferences,
            )
            if priority_candidates:
                return self._refresh_priority_candidates_with_realtime_routes(
                    candidates=priority_candidates,
                    candidate_records=priority_records,
                    current_location=current_location,
                    transport_mode=transport_mode,
                    triage=triage,
                    preferences=preferences,
                )

        rough_candidates = [
            self._score_hospital(
                hospital=hospital,
                current_location=current_location,
                transport_mode=transport_mode,
                triage=triage,
                preferences=preferences,
                use_realtime_route=False,
            )
            for hospital in candidate_records
        ]
        rough_candidates.sort(key=lambda item: item.score_breakdown.final_score, reverse=True)

        realtime_ids = {
            candidate.hospital_id
            for candidate in rough_candidates[: max(1, min(settings.realtime_route_limit, len(rough_candidates)))]
        }

        with ThreadPoolExecutor(max_workers=min(4, len(candidate_records))) as executor:
            results = list(
                executor.map(
                    lambda hospital: self._score_hospital(
                        hospital=hospital,
                        current_location=current_location,
                        transport_mode=transport_mode,
                        triage=triage,
                        preferences=preferences,
                        use_realtime_route=hospital["id"] in realtime_ids,
                    ),
                    candidate_records,
                )
            )

        candidates = [candidate for candidate in results if candidate is not None]
        candidates = sorted(candidates, key=lambda item: item.score_breakdown.final_score, reverse=True)

        if candidates and candidates[0].hospital_id not in realtime_ids:
            top_hospital = next(
                (hospital for hospital in candidate_records if hospital["id"] == candidates[0].hospital_id),
                None,
            )
            if top_hospital is not None:
                refreshed_top = self._score_hospital(
                    hospital=top_hospital,
                    current_location=current_location,
                    transport_mode=transport_mode,
                    triage=triage,
                    preferences=preferences,
                    use_realtime_route=True,
                )
                candidates[0] = refreshed_top
                candidates = sorted(candidates, key=lambda item: item.score_breakdown.final_score, reverse=True)

        return self._refresh_final_candidates_with_realtime_routes(
            candidates=candidates,
            candidate_records=candidate_records,
            current_location=current_location,
            transport_mode=transport_mode,
            triage=triage,
            preferences=preferences,
        )

    def _refresh_final_candidates_with_realtime_routes(
        self,
        candidates: List[HospitalCandidate],
        candidate_records: List[Dict],
        current_location: str,
        transport_mode: TransportMode,
        triage: TriageResult,
        preferences: Preferences,
    ) -> List[HospitalCandidate]:
        top_candidates = candidates[: settings.max_candidate_results]
        if not top_candidates:
            return []

        record_lookup = {record["id"]: record for record in candidate_records}
        selected_records = [
            record_lookup[candidate.hospital_id]
            for candidate in top_candidates
            if candidate.hospital_id in record_lookup
        ]
        if not selected_records:
            return top_candidates

        refreshed = [
            self._score_hospital(
                hospital=hospital,
                current_location=current_location,
                transport_mode=transport_mode,
                triage=triage,
                preferences=preferences,
                use_realtime_route=True,
            )
            for hospital in selected_records
        ]

        refreshed_candidates = [candidate for candidate in refreshed if candidate is not None]
        refreshed_candidates.sort(key=lambda item: item.score_breakdown.final_score, reverse=True)
        return refreshed_candidates[: settings.max_candidate_results]

    def _refresh_priority_candidates_with_realtime_routes(
        self,
        candidates: List[HospitalCandidate],
        candidate_records: List[Dict],
        current_location: str,
        transport_mode: TransportMode,
        triage: TriageResult,
        preferences: Preferences,
    ) -> List[HospitalCandidate]:
        top_candidates = candidates[: settings.max_candidate_results]
        if not top_candidates:
            return []

        record_lookup = {record["id"]: record for record in candidate_records}
        selected_records = [
            record_lookup[candidate.hospital_id]
            for candidate in top_candidates
            if candidate.hospital_id in record_lookup
        ]
        if not selected_records:
            return top_candidates

        refreshed = [
            self._score_hospital(
                hospital=hospital,
                current_location=current_location,
                transport_mode=transport_mode,
                triage=triage,
                preferences=preferences,
                use_realtime_route=True,
            )
            for hospital in selected_records
        ]
        refreshed_candidates = [candidate for candidate in refreshed if candidate is not None]
        refreshed_candidates.sort(
            key=lambda item: (
                item.score_breakdown.travel_minutes,
                item.score_breakdown.transfer_count,
                -self._priority_level_rank(item.hospital_level),
                -item.score_breakdown.final_score,
            )
        )
        return refreshed_candidates[: settings.max_candidate_results]

    def _fallback_local_records(
        self,
        current_location: str,
        triage: TriageResult,
        local_hospitals: List[Dict],
    ) -> List[Dict]:
        origin_context = self.map_service.resolve_location(current_location)
        eligible_hospitals = []
        origin_city = self._normalize_city_name(origin_context.city if origin_context else "")

        for hospital in local_hospitals:
            if triage.department not in hospital["departments"]:
                continue
            if origin_context is not None:
                hospital_context = self.map_service.resolve_location(hospital["address"])
                hospital_city = self._normalize_city_name(hospital_context.city if hospital_context else "")
                if hospital_context is None or hospital_city != origin_city:
                    continue
            eligible_hospitals.append(hospital)
        return eligible_hospitals

    def _build_live_record(
        self,
        nearby: NearbyHospital,
        triage: TriageResult,
        matched_local: Optional[Dict],
        matched_priority: Optional[Dict],
        display_name: str,
    ) -> Dict:
        booking_url = self._resolve_booking_url(display_name, matched_local, matched_priority)
        transport_profiles = self._estimate_transport_profiles(nearby.distance_meters)
        departments = (
            matched_local["departments"]
            if matched_local
            else [triage.department, "全科医学科"]
        )
        crowd_level = (
            matched_local["crowd_level"]
            if matched_local
            else self._estimate_crowd_level(nearby)
        )
        hospital_level = (
            self._normalize_hospital_level(matched_priority.get("hospital_level")) if matched_priority else None
        )
        if hospital_level is None:
            hospital_level = (
                self._normalize_hospital_level(matched_local.get("hospital_level")) if matched_local else None
            )
        if hospital_level is None:
            hospital_level = self._estimate_hospital_level(nearby)
        layout = (
            matched_local["layout"]
            if matched_local
            else {
                triage.department: "请先前往门诊大厅导医台确认挂号与候诊区域",
                "全科医学科": "请先前往门诊大厅导医台确认挂号与候诊区域",
            }
        )
        availability = (
            matched_local["availability"]
            if matched_local
            else {triage.department: ["dynamic-slot"], "全科医学科": ["dynamic-slot"]}
        )
        elder_features = (
            matched_local["elder_friendly_features"]
            if matched_local
            else ["官网可查询门诊信息", "建议先到导医台确认就诊科室"]
        )

        return {
            "id": f"live-{nearby.poi_id}",
            "name": display_name,
            "address": nearby.address or nearby.name,
            "hospital_level": hospital_level,
            "booking_url": booking_url,
            "nearby_regions": [nearby.district] if nearby.district else [nearby.city],
            "departments": departments,
            "crowd_level": crowd_level,
            "elder_friendly_features": elder_features,
            "transport_profiles": transport_profiles,
            "availability": availability,
            "layout": layout,
            "live_distance_meters": nearby.distance_meters,
            "live_type": nearby.type,
            "live_keytag": nearby.keytag,
            "source": "live",
        }

    def _build_priority_records(self, priority_hospitals: List[Dict], triage: TriageResult) -> List[Dict]:
        records = []
        for hospital in priority_hospitals:
            destination_address = f"{hospital['city']}{hospital['destination_query']}"
            display_address = f"{hospital['city']} · {hospital['hospital_name']}"
            records.append(
                {
                    "id": f"priority-{hospital['hospital_id']}",
                    "name": hospital["hospital_name"],
                    "address": display_address,
                    "route_destination": destination_address,
                    "hospital_level": hospital["hospital_level"],
                    "booking_url": hospital["official_url"],
                    "nearby_regions": [hospital["city"]],
                    "departments": [triage.department, "全科医学科"],
                    "crowd_level": 0.56 if hospital["hospital_level"] == "三甲" else 0.42,
                    "elder_friendly_features": ["官网可直接查看医院信息", "建议到院后先到导医台分诊"],
                    "transport_profiles": self._estimate_transport_profiles(6500 if hospital["hospital_level"] == "三甲" else 4800),
                    "availability": {triage.department: ["priority-slot"], "全科医学科": ["priority-slot"]},
                    "layout": {
                        triage.department: "请先前往门诊大厅导医台确认挂号与候诊区域",
                        "全科医学科": "请先前往门诊大厅导医台确认挂号与候诊区域",
                    },
                    "source": "xian_priority_db",
                }
            )
        return records

    def _score_priority_hospitals(
        self,
        candidate_records: List[Dict],
        current_location: str,
        transport_mode: TransportMode,
        triage: TriageResult,
        preferences: Preferences,
    ) -> List[HospitalCandidate]:
        candidates = [
            self._score_hospital(
                hospital=hospital,
                current_location=current_location,
                transport_mode=transport_mode,
                triage=triage,
                preferences=preferences,
                use_realtime_route=False,
            )
            for hospital in candidate_records
        ]
        candidates.sort(
            key=lambda item: (
                item.score_breakdown.travel_minutes,
                item.score_breakdown.transfer_count,
                -self._priority_level_rank(item.hospital_level),
                -item.score_breakdown.final_score,
            )
        )
        return candidates

    def _score_hospital(
        self,
        hospital: Dict,
        current_location: str,
        transport_mode: TransportMode,
        triage: TriageResult,
        preferences: Preferences,
        use_realtime_route: bool,
    ) -> HospitalCandidate:
        travel_profile = hospital["transport_profiles"][transport_mode.value]
        if use_realtime_route:
            route_result = self.map_service.plan_route(
                origin=current_location,
                destination=hospital.get("route_destination", hospital["address"]),
                transport_mode=transport_mode,
                fallback_profile=travel_profile,
                nearby_regions=hospital["nearby_regions"],
            )
        else:
            route_result = MapRouteResult(
                travel_minutes=int(travel_profile.get("base_minutes", 30)),
                transfer_count=int(travel_profile.get("transfers", 0)),
                route_summary=travel_profile.get("route", "路线信息待补充"),
                route_steps=self.map_service._fallback_steps(
                    transport_mode,
                    int(travel_profile.get("base_minutes", 30)),
                    int(travel_profile.get("transfers", 0)),
                ),
                provider="mock",
            )

        travel_minutes = route_result.travel_minutes
        transfer_count = route_result.transfer_count
        crowd_level = hospital["crowd_level"]
        availability_bonus = 14 if hospital["availability"].get(triage.department) else 6
        elder_friendly_bonus = 8 if preferences.mobility_support_needed else 3
        department_match = self._department_match_score(triage.department, hospital)

        transfer_penalty = transfer_count * (12 if preferences.prefer_direct_route else 8)
        crowd_penalty = crowd_level * (22 if preferences.prefer_low_crowd else 14)
        score = round(
            100
            - (travel_minutes * 0.75)
            - transfer_penalty
            - crowd_penalty
            + department_match
            + availability_bonus
            + elder_friendly_bonus,
            2,
        )

        reasons = [
            f"距您当前位置预计{travel_minutes}分钟可到达",
            f"{triage.department}可挂号资源{'较充足' if availability_bonus > 10 else '可进一步确认'}",
            f"当前拥挤度约为{int(crowd_level * 100)}%，对老年用户相对友好",
        ]
        if transfer_count == 0:
            reasons.append("路线较简单，尽量减少换乘。")
        if route_result.provider != "mock":
            reasons.append(f"已调用{route_result.provider}路线规划获取实时路程。")
        elif use_realtime_route is False:
            reasons.append("当前其余候选医院先展示估算路线，确认后可再刷新实时路线。")
        if hospital.get("source") == "live":
            reasons.append("该医院来自高德实时附近医院检索。")

        return HospitalCandidate(
            hospital_id=hospital["id"],
            hospital_name=hospital["name"],
            address=hospital["address"],
            hospital_level=hospital.get("hospital_level"),
            booking_url=hospital.get("booking_url"),
            route=route_result.route_summary,
            route_steps=route_result.route_steps,
            reasons=reasons,
            score_breakdown=ScoreBreakdown(
                travel_minutes=travel_minutes,
                transfer_count=transfer_count,
                crowd_level=crowd_level,
                department_match=department_match,
                availability_bonus=availability_bonus,
                elder_friendly_bonus=elder_friendly_bonus,
                final_score=score,
            ),
        )

    @staticmethod
    def _resolve_booking_url(
        name: str,
        matched_local: Optional[Dict],
        matched_priority: Optional[Dict],
    ) -> str:
        if matched_priority and matched_priority.get("official_url"):
            return matched_priority["official_url"]
        if matched_local and matched_local.get("booking_url"):
            return matched_local["booking_url"]
        return f"https://www.baidu.com/s?wd={quote_plus(f'{name} 官网')}"

    @staticmethod
    def _estimate_crowd_level(nearby: NearbyHospital) -> float:
        label = f"{nearby.keytag} {nearby.type}"
        if "三甲" in label or "三级甲等" in label:
            return 0.58
        if "专科医院" in label:
            return 0.42
        if "社区" in label or "卫生院" in label:
            return 0.26
        if "中医" in label:
            return 0.34
        return 0.4

    @staticmethod
    def _estimate_hospital_level(nearby: NearbyHospital) -> str:
        label = f"{nearby.keytag} {nearby.type} {nearby.name}"
        if "三甲" in label or "三级甲等" in label:
            return "三甲"
        if "二甲" in label or "二级甲等" in label:
            return "二甲"
        if "三级" in label:
            return "三级"
        if "二级" in label:
            return "二级"
        return "未定级"

    @staticmethod
    def _normalize_hospital_level(raw_level: Optional[str]) -> Optional[str]:
        if not raw_level:
            return None

        text = str(raw_level).strip()
        if not text:
            return None
        if "三甲" in text or "三级甲等" in text:
            return "三甲"
        if "二甲" in text or "二级甲等" in text:
            return "二甲"
        if "三级" in text:
            return "三级"
        if "二级" in text:
            return "二级"
        if text in {"未定级", "暂未定级", "未标注"}:
            return "未定级"
        return None

    @staticmethod
    def _priority_level_rank(level: Optional[str]) -> int:
        if level == "三甲":
            return 4
        if level == "二甲":
            return 3
        if level == "三级":
            return 2
        if level == "二级":
            return 1
        return 0

    @staticmethod
    def _normalize_city_name(city: str) -> str:
        text = str(city or "").strip()
        if not text:
            return ""
        if text.endswith("市"):
            return text
        return f"{text}市"

    @staticmethod
    def _estimate_transport_profiles(distance_meters: int) -> Dict[str, Dict]:
        walking_minutes = max(12, round(distance_meters / 70))
        bus_minutes = max(10, round(distance_meters / 220))
        metro_minutes = max(12, round(distance_meters / 280))
        taxi_minutes = max(8, round(distance_meters / 450))
        return {
            "walking": {
                "base_minutes": walking_minutes,
                "transfers": 0,
                "route": f"从当前位置步行前往医院，预计约 {walking_minutes} 分钟。",
            },
            "bus": {
                "base_minutes": bus_minutes,
                "transfers": 1 if distance_meters > 2500 else 0,
                "route": f"先前往附近公交站，再乘公交到医院附近，预计约 {bus_minutes} 分钟。",
            },
            "metro": {
                "base_minutes": metro_minutes,
                "transfers": 1 if distance_meters > 4000 else 0,
                "route": f"先前往最近地铁站，乘地铁到医院附近站点，再步行到院，预计约 {metro_minutes} 分钟。",
            },
            "taxi": {
                "base_minutes": taxi_minutes,
                "transfers": 0,
                "route": f"建议直接打车前往医院门口，预计约 {taxi_minutes} 分钟。",
            },
        }

    @staticmethod
    def _department_match_score(department: str, hospital: Dict) -> int:
        if department in hospital.get("departments", []):
            return 20

        name_and_type = f"{hospital.get('name', '')} {hospital.get('live_type', '')}"
        if any(keyword in name_and_type for keyword in ("儿童", "妇幼", "口腔", "皮肤", "精神", "男科", "整形")):
            return 4
        if department == "呼吸内科" and any(keyword in name_and_type for keyword in ("胸科", "呼吸")):
            return 20
        if department == "骨科" and any(keyword in name_and_type for keyword in ("骨", "创伤")):
            return 20
        if department == "神经内科" and "神经" in name_and_type:
            return 20
        if department == "心内科" and any(keyword in name_and_type for keyword in ("心", "胸")):
            return 18
        if any(keyword in name_and_type for keyword in ("综合医院", "三级甲等医院", "专科医院", "医院")):
            return 16
        return 10

    @staticmethod
    def _normalize_hospital_name(name: str) -> str:
        cleaned = (
            name.replace("（", "(")
            .replace("）", ")")
            .replace("总院", "")
            .replace("东院区", "")
            .replace("西院区", "")
            .replace("南院区", "")
            .replace("北院区", "")
            .replace("门诊部", "")
            .replace("门诊", "")
            .replace("住院部", "")
            .replace("总院区", "")
            .strip()
        )
        if "(" in cleaned:
            cleaned = cleaned.split("(", 1)[0].strip()
        return cleaned.replace(" ", "")

    @staticmethod
    def _simplify_live_hospital_name(name: str) -> str:
        if "医院" in name:
            return name.split("医院", 1)[0].strip() + "医院"
        return name.strip()

    def _match_local_hospital(self, normalized_name: str, local_lookup: Dict[str, Dict]) -> Optional[Dict]:
        exact = local_lookup.get(normalized_name)
        if exact is not None:
            return exact

        for local_name, hospital in local_lookup.items():
            if local_name in normalized_name or normalized_name in local_name:
                return hospital
        return None

    def _is_relevant_live_hospital(self, hospital_name: str, department: str) -> bool:
        desired_hints = self.DEPARTMENT_HINTS.get(department, set())
        matched_desired = any(hint in hospital_name for hint in desired_hints)

        for other_department, hints in self.DEPARTMENT_HINTS.items():
            if other_department == department:
                continue
            if any(hint in hospital_name for hint in hints):
                return matched_desired
        return True
