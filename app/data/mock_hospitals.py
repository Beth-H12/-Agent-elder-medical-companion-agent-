from urllib.parse import quote_plus


def official_site(url: str) -> str:
    return url


def browser_search(name: str) -> str:
    return f"https://www.baidu.com/s?wd={quote_plus(f'{name} 官网')}"


HOSPITALS = [
    {
        "id": "east-care",
        "name": "东方惠民医院",
        "address": "上海市浦东新区康宁路88号",
        "hospital_level": "未定级",
        "booking_url": browser_search("东方惠民医院"),
        "nearby_regions": ["浦东新区", "黄浦区"],
        "departments": ["心内科", "呼吸内科", "神经内科", "全科医学科"],
        "crowd_level": 0.35,
        "elder_friendly_features": ["无障碍电梯", "志愿者导诊", "门诊轮椅服务"],
        "transport_profiles": {
            "walking": {"base_minutes": 70, "transfers": 0, "route": "步行约70分钟，不建议长时间步行前往。"},
            "bus": {"base_minutes": 42, "transfers": 1, "route": "乘坐公交785路，医院站下车后步行120米。"},
            "metro": {"base_minutes": 25, "transfers": 0, "route": "地铁2号线直达，出站步行300米。"},
            "taxi": {"base_minutes": 18, "transfers": 0, "route": "打车约18分钟，可直接到门诊楼下客区。"},
        },
        "availability": {
            "心内科": ["2026-04-10 09:30", "2026-04-10 10:20", "2026-04-10 14:30"],
            "呼吸内科": ["2026-04-10 09:00", "2026-04-10 15:00"],
            "神经内科": ["2026-04-10 10:00", "2026-04-11 09:30"],
            "全科医学科": ["2026-04-10 08:40", "2026-04-10 13:40"],
        },
        "layout": {
            "心内科": "门诊楼2层A区12诊室",
            "呼吸内科": "门诊楼3层B区6诊室",
            "神经内科": "门诊楼2层C区5诊室",
            "全科医学科": "门诊楼1层便民门诊",
        },
    },
    {
        "id": "jing-an-general",
        "name": "静安人民医院",
        "address": "上海市静安区平安路120号",
        "hospital_level": "未定级",
        "booking_url": browser_search("静安人民医院"),
        "nearby_regions": ["静安区", "黄浦区", "徐汇区"],
        "departments": ["心内科", "消化内科", "神经内科", "骨科"],
        "crowd_level": 0.58,
        "elder_friendly_features": ["老年绿色通道", "自助机人工辅导"],
        "transport_profiles": {
            "walking": {"base_minutes": 90, "transfers": 0, "route": "步行距离较远，建议选择公交或地铁。"},
            "bus": {"base_minutes": 48, "transfers": 2, "route": "公交41路换乘112路，到人民医院站下车。"},
            "metro": {"base_minutes": 32, "transfers": 1, "route": "地铁1号线换乘7号线，出站步行220米。"},
            "taxi": {"base_minutes": 22, "transfers": 0, "route": "打车约22分钟，院内设有无障碍入口。"},
        },
        "availability": {
            "心内科": ["2026-04-10 11:10", "2026-04-10 15:10"],
            "消化内科": ["2026-04-10 09:20", "2026-04-10 13:20"],
            "神经内科": ["2026-04-10 14:00", "2026-04-11 09:10"],
            "骨科": ["2026-04-10 10:40", "2026-04-10 16:00"],
        },
        "layout": {
            "心内科": "门诊楼3层东区18诊室",
            "消化内科": "门诊楼2层西区7诊室",
            "神经内科": "门诊楼4层北区3诊室",
            "骨科": "门诊楼1层创伤门诊区",
        },
    },
    {
        "id": "xuhui-friendly",
        "name": "徐汇康宁医院",
        "address": "上海市徐汇区安福路66号",
        "hospital_level": "未定级",
        "booking_url": browser_search("徐汇康宁医院"),
        "nearby_regions": ["徐汇区", "长宁区"],
        "departments": ["呼吸内科", "全科医学科", "心内科", "内分泌科"],
        "crowd_level": 0.28,
        "elder_friendly_features": ["老年陪诊台", "免费轮椅借用", "一层导医服务"],
        "transport_profiles": {
            "walking": {"base_minutes": 75, "transfers": 0, "route": "步行较远，建议乘车。"},
            "bus": {"base_minutes": 36, "transfers": 0, "route": "公交927路直达，医院南门站下车。"},
            "metro": {"base_minutes": 29, "transfers": 0, "route": "地铁9号线直达，2号口出站后步行260米。"},
            "taxi": {"base_minutes": 20, "transfers": 0, "route": "打车约20分钟，方便上下车。"},
        },
        "availability": {
            "呼吸内科": ["2026-04-10 09:10", "2026-04-10 09:50", "2026-04-10 14:10"],
            "全科医学科": ["2026-04-10 08:30", "2026-04-10 11:30"],
            "心内科": ["2026-04-10 10:30", "2026-04-10 15:00"],
            "内分泌科": ["2026-04-10 14:40", "2026-04-11 09:00"],
        },
        "layout": {
            "呼吸内科": "门诊楼2层呼吸专病区",
            "全科医学科": "门诊楼1层综合门诊区",
            "心内科": "门诊楼2层心血管区8诊室",
            "内分泌科": "门诊楼3层代谢门诊区",
        },
    },
    {
        "id": "yangpu-senior",
        "name": "康和老年友好医院",
        "address": "上海市杨浦区安康大道18号",
        "hospital_level": "未定级",
        "booking_url": browser_search("康和老年友好医院"),
        "nearby_regions": ["杨浦区", "虹口区"],
        "departments": ["神经内科", "骨科", "全科医学科", "心内科"],
        "crowd_level": 0.31,
        "elder_friendly_features": ["老年门诊优先叫号", "护士站陪同指引", "停车即停即下"],
        "transport_profiles": {
            "walking": {"base_minutes": 85, "transfers": 0, "route": "步行较远，不建议独自前往。"},
            "bus": {"base_minutes": 34, "transfers": 1, "route": "乘坐公交155路，换乘一次后在康和医院站下车。"},
            "metro": {"base_minutes": 27, "transfers": 0, "route": "地铁8号线直达，出站步行180米。"},
            "taxi": {"base_minutes": 19, "transfers": 0, "route": "打车约19分钟，门口有导诊志愿者。"},
        },
        "availability": {
            "神经内科": ["2026-04-10 09:40", "2026-04-10 13:50"],
            "骨科": ["2026-04-10 10:10", "2026-04-10 15:40"],
            "全科医学科": ["2026-04-10 08:50", "2026-04-10 13:20"],
            "心内科": ["2026-04-10 09:20", "2026-04-10 14:20"],
        },
        "layout": {
            "神经内科": "门诊楼3层老年神经区",
            "骨科": "门诊楼2层骨伤门诊区",
            "全科医学科": "门诊楼1层老年综合服务区",
            "心内科": "门诊楼2层西侧10诊室",
        },
    },
    {
        "id": "xian-medical-college-first",
        "name": "西安医学院第一附属医院",
        "address": "陕西省西安市莲湖区西安医学院第一附属医院",
        "hospital_level": "三甲",
        "booking_url": official_site("https://www.xyfy.com.cn/"),
        "nearby_regions": ["莲湖区", "新城区", "碑林区"],
        "departments": ["心内科", "呼吸内科", "神经内科", "全科医学科"],
        "crowd_level": 0.34,
        "elder_friendly_features": ["门诊志愿者服务", "老年优先窗口", "轮椅借用"],
        "transport_profiles": {
            "walking": {"base_minutes": 24, "transfers": 0, "route": "步行约24分钟，建议有人陪同前往。"},
            "bus": {"base_minutes": 18, "transfers": 0, "route": "公交直达，医院站下车后步行约150米。"},
            "metro": {"base_minutes": 20, "transfers": 1, "route": "地铁换乘一次后步行约220米到院。"},
            "taxi": {"base_minutes": 12, "transfers": 0, "route": "打车约12分钟，可直接到门诊入口。"},
        },
        "availability": {
            "心内科": ["2026-04-10 09:20", "2026-04-10 10:10", "2026-04-10 14:20"],
            "呼吸内科": ["2026-04-10 09:00", "2026-04-10 14:40"],
            "神经内科": ["2026-04-10 10:40", "2026-04-11 09:20"],
            "全科医学科": ["2026-04-10 08:50", "2026-04-10 13:50"],
        },
        "layout": {
            "心内科": "门诊楼2层心血管门诊区",
            "呼吸内科": "门诊楼3层呼吸专科区",
            "神经内科": "门诊楼2层东侧6诊室",
            "全科医学科": "门诊楼1层便民综合门诊",
        },
    },
    {
        "id": "xian-central",
        "name": "西安市中心医院",
        "address": "陕西省西安市中心医院",
        "hospital_level": "三甲",
        "booking_url": official_site("https://xaszxyy.com/"),
        "nearby_regions": ["新城区", "莲湖区", "碑林区"],
        "departments": ["心内科", "呼吸内科", "消化内科", "神经内科"],
        "crowd_level": 0.46,
        "elder_friendly_features": ["老年人导诊服务", "院内无障碍电梯"],
        "transport_profiles": {
            "walking": {"base_minutes": 36, "transfers": 0, "route": "步行距离较长，建议优先公交或地铁。"},
            "bus": {"base_minutes": 20, "transfers": 1, "route": "公交换乘一次后到医院门口。"},
            "metro": {"base_minutes": 18, "transfers": 0, "route": "地铁直达，出站后步行约260米。"},
            "taxi": {"base_minutes": 14, "transfers": 0, "route": "打车约14分钟，门口上下车方便。"},
        },
        "availability": {
            "心内科": ["2026-04-10 09:40", "2026-04-10 15:10"],
            "呼吸内科": ["2026-04-10 10:20", "2026-04-10 14:30"],
            "消化内科": ["2026-04-10 09:10", "2026-04-10 13:20"],
            "神经内科": ["2026-04-10 11:00", "2026-04-11 09:40"],
        },
        "layout": {
            "心内科": "门诊楼3层心内科门诊",
            "呼吸内科": "门诊楼2层呼吸门诊区",
            "消化内科": "门诊楼2层西区8诊室",
            "神经内科": "门诊楼4层神经门诊区",
        },
    },
    {
        "id": "xian-people",
        "name": "西安市人民医院",
        "address": "陕西省西安市长安区西安市人民医院",
        "hospital_level": "三甲",
        "booking_url": official_site("https://www.grmg.com.cn/"),
        "nearby_regions": ["长安区", "碑林区", "雁塔区"],
        "departments": ["心内科", "全科医学科", "内分泌科", "呼吸内科"],
        "crowd_level": 0.38,
        "elder_friendly_features": ["老年综合服务台", "门诊陪诊志愿者"],
        "transport_profiles": {
            "walking": {"base_minutes": 110, "transfers": 0, "route": "步行不建议，优先选择公共交通。"},
            "bus": {"base_minutes": 52, "transfers": 1, "route": "公交换乘一次可到医院。"},
            "metro": {"base_minutes": 42, "transfers": 1, "route": "地铁换乘一次后步行约300米。"},
            "taxi": {"base_minutes": 28, "transfers": 0, "route": "打车约28分钟，方便到达门诊入口。"},
        },
        "availability": {
            "心内科": ["2026-04-10 10:00", "2026-04-10 14:50"],
            "全科医学科": ["2026-04-10 08:40", "2026-04-10 11:10"],
            "内分泌科": ["2026-04-10 09:30", "2026-04-10 15:20"],
            "呼吸内科": ["2026-04-10 10:50", "2026-04-10 14:10"],
        },
        "layout": {
            "心内科": "门诊楼2层A区9诊室",
            "全科医学科": "门诊楼1层综合门诊区",
            "内分泌科": "门诊楼3层代谢门诊区",
            "呼吸内科": "门诊楼2层呼吸诊区",
        },
    },
]


ALL_DEPARTMENTS = sorted(
    {department for hospital in HOSPITALS for department in hospital["departments"]}
)
