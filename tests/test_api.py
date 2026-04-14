from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.controller import MedicalCompanionController
from app.agents.triage_agent import LLMTriageAgent, RuleBasedTriageAgent
from app.api.routes import get_controller
from app.db.database import init_db
from app.main import app
from app.schemas.models import IntakeRequest
from app.services.map_service import MapService


def setup_function() -> None:
    init_db()
    get_controller.cache_clear()
    controller = get_controller()
    controller.store.clear()
    controller.document_storage.clear()


def test_full_medical_flow() -> None:
    with TestClient(app) as client:
        health_response = client.get("/api/health")
        assert health_response.status_code == 200
        health_payload = health_response.json()
        assert health_payload["llm_provider"] == "ollama"
        assert health_payload["map_provider"] == "amap"

        intake_response = client.post(
            "/api/intake",
            json={
                "current_location": "浦东新区",
                "transport_mode": "metro",
                "preferred_time": "明天上午",
                "symptom_text": "最近胸口发闷，有时候喘不上气，走快一点就难受。",
            },
        )
        assert intake_response.status_code == 200
        intake_payload = intake_response.json()
        assert intake_payload["triage"]["department"] == "心内科"
        assert intake_payload["recommended_hospital"]["hospital_name"]
        assert intake_payload["recommended_hospital"]["route"]
        assert intake_payload["recommended_hospital"]["route_steps"]
        assert intake_payload["recommended_hospital"]["booking_url"]
        assert len(intake_payload["candidates"]) == 3
        assert "guahao.com" not in intake_payload["recommended_hospital"]["booking_url"]

        session_id = intake_payload["session_id"]
        booking_response = client.post(
            "/api/appointments/book",
            json={"session_id": session_id},
        )
        assert booking_response.status_code == 200
        booking_payload = booking_response.json()
        assert booking_payload["appointment"]["status"] in {"success", "pending_official_booking"}
        assert booking_payload["appointment"]["location"]
        assert booking_payload["appointment"]["route"]
        assert booking_payload["appointment"]["route_steps"]
        assert booking_payload["appointment"]["booking_url"]
        assert "guahao.com" not in booking_payload["appointment"]["booking_url"]

        document_response = client.post(
            "/api/documents/archive",
            json={
                "session_id": session_id,
                "document_title": "血常规复查报告",
                "document_text": "\n".join(
                    [
                        "东方惠民医院",
                        "心内科",
                        "2026-04-10",
                        "血常规",
                        "白细胞 7.5",
                        "红细胞 4.6",
                        "门诊建议：一周后复诊，按时服药。",
                    ]
                ),
            },
        )
        assert document_response.status_code == 200
        document_payload = document_response.json()
        assert document_payload["archived_document"]["doc_type"] == "血常规报告"
        assert document_payload["care_instructions"]["follow_up_needed"] is True

        session_response = client.get(f"/api/sessions/{session_id}")
        assert session_response.status_code == 200
        session_payload = session_response.json()
        assert len(session_payload["documents"]) == 1
        assert len(session_payload["agent_trace"]) >= 6


def test_unknown_session_returns_404() -> None:
    with TestClient(app) as client:
        response = client.post("/api/appointments/book", json={"session_id": "missing-session"})
        assert response.status_code == 404


def test_xian_location_returns_xian_hospital() -> None:
    with TestClient(app) as client:
        intake_response = client.post(
            "/api/intake",
            json={
                "current_location": "西安市莲湖区早慈巷",
                "transport_mode": "metro",
                "preferred_time": "明天上午",
                "symptom_text": "最近胸口发闷，有时候喘不上气，走快一点就难受。",
            },
        )
        assert intake_response.status_code == 200
        intake_payload = intake_response.json()
        assert "西安市" in intake_payload["recommended_hospital"]["address"]
        assert "上海" not in intake_payload["recommended_hospital"]["address"]
        assert intake_payload["recommended_hospital"]["booking_url"]
        assert len(intake_payload["candidates"]) == 3
        assert "guahao.com" not in intake_payload["recommended_hospital"]["booking_url"]


def test_session_persists_across_controller_instances() -> None:
    intake_request = IntakeRequest(
        current_location="浦东新区",
        transport_mode="metro",
        preferred_time="明天上午",
        symptom_text="最近胸口发闷，有时候喘不上气，走快一点就难受。",
    )

    first_controller = MedicalCompanionController()
    intake_response = first_controller.handle_intake(intake_request)

    second_controller = MedicalCompanionController()
    persisted_session = second_controller.get_session(intake_response.session_id)

    assert persisted_session.session_id == intake_response.session_id
    assert persisted_session.triage.department == "心内科"
    assert persisted_session.candidates[0].hospital_name


def test_archive_document_image_upload() -> None:
    with TestClient(app) as client:
        intake_response = client.post(
            "/api/intake",
            json={
                "current_location": "西安市莲湖区早慈巷",
                "transport_mode": "metro",
                "preferred_time": "明天上午",
                "symptom_text": "最近胸口发闷，有时候喘不上气，走快一点就难受。",
            },
        )
        assert intake_response.status_code == 200
        session_id = intake_response.json()["session_id"]

        document_response = client.post(
            "/api/documents/archive-image",
            data={
                "session_id": session_id,
                "document_title": "心电图检查单",
                "document_text": "",
                "uploaded_from": "image_upload",
                "issue_status": "有问题",
            },
            files={
                "document_image": ("ecg-report.jpg", b"fake-image-bytes", "image/jpeg"),
            },
        )
        assert document_response.status_code == 200
        payload = document_response.json()
        assert payload["archived_document"]["source_filename"] == "ecg-report.jpg"
        assert payload["archived_document"]["issue_status"] == "有问题"
        assert payload["archived_document"]["source_image_url"].startswith("/static/medical_records/")
        assert payload["archived_document"]["storage_directory"].endswith("/有问题")
        assert payload["archived_document"]["note_file_url"].startswith("/static/medical_records/")
        assert payload["archived_document"]["summary"]


def test_text_archive_saved_under_date_department_and_issue_bucket() -> None:
    with TestClient(app) as client:
        intake_response = client.post(
            "/api/intake",
            json={
                "current_location": "西安市莲湖区早慈巷",
                "transport_mode": "metro",
                "preferred_time": "明天上午",
                "symptom_text": "最近胸口发闷，有时候喘不上气，走快一点就难受。",
            },
        )
        session_id = intake_response.json()["session_id"]

        document_response = client.post(
            "/api/documents/archive",
            json={
                "session_id": session_id,
                "document_title": "血常规复查报告",
                "document_text": "\n".join(
                    [
                        "西安市中心医院",
                        "心内科",
                        "2026-04-10",
                        "血常规",
                        "门诊建议：继续观察，按时复诊。",
                    ]
                ),
                "issue_status": "无问题",
            },
        )

        assert document_response.status_code == 200
        payload = document_response.json()
        assert payload["archived_document"]["issue_status"] == "无问题"
        assert "/2026-04-10-心内科/无问题" in payload["archived_document"]["storage_directory"]
        note_url = payload["archived_document"]["note_file_url"]
        note_path = Path("E:/hospital/static") / note_url.removeprefix("/static/")
        assert note_path.exists()


def test_elderly_mild_dizziness_can_observe_briefly() -> None:
    agent = RuleBasedTriageAgent()
    result = agent.run("这两天有一点头晕和轻微恶心，但能正常吃饭走路，没有胸痛也没有呕吐。")

    assert result.urgency == "routine"
    assert result.risk_flag is False
    assert "先短时在家观察" in result.advice


def test_elderly_palpitations_and_stomach_cramps_need_soon_visit() -> None:
    agent = RuleBasedTriageAgent()

    palpitations = agent.run("老人这两天总是心慌，稍微活动一下就更明显。")
    stomach_cramps = agent.run("老人今天胃绞痛，还拉肚子、恶心，怀疑急性肠胃炎。")

    assert palpitations.urgency in {"soon", "urgent"}
    assert palpitations.department == "心内科"
    assert stomach_cramps.urgency in {"soon", "urgent"}
    assert stomach_cramps.department == "消化内科"


def test_elderly_fracture_is_not_routine() -> None:
    agent = RuleBasedTriageAgent()
    result = agent.run("老人摔倒后怀疑骨折，腿肿得厉害，走不了路。")

    assert result.department == "骨科"
    assert result.urgency in {"soon", "urgent"}


def test_llm_guardrail_helper_no_longer_crashes() -> None:
    assert LLMTriageAgent._should_prefer_rule_routine(
        "这两天有一点头晕和轻微恶心，但没有胸痛。",
        RuleBasedTriageAgent().run("这两天有一点头晕和轻微恶心，但没有胸痛。"),
    ) is True


def test_extract_transit_steps_contains_line_station_exit_and_walking_distance() -> None:
    service = MapService()
    segments = [
        {
            "walking": {"distance": "320", "steps": []},
            "bus": {
                "buslines": [
                    {
                        "name": "地铁2号线(韦曲南-北客站)",
                        "departure_stop": {"name": "小寨"},
                        "arrival_stop": {"name": "钟楼"},
                        "via_num": "4",
                    }
                ]
            },
        },
        {
            "walking": {
                "distance": "180",
                "steps": [{"assistant_action": "到达西安市中心医院"}],
            },
            "bus": {"buslines": []},
            "exit": {"name": "A口"},
        },
    ]

    steps = service._extract_transit_steps(segments, "西安市中心医院")

    assert steps[0] == "先步行约 320 米，到 小寨 站进站。"
    assert "乘坐 地铁2号线，从 小寨 站上车，到 钟楼 站下车，途经 4 站。" in steps
    assert steps[-1] == "从 钟楼站A口 出站后步行约 180 米，到达 西安市中心医院。"
