from pathlib import Path
from io import BytesIO
from types import SimpleNamespace
from PIL import Image, ImageDraw
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import build_pdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "sample_output.pdf"


def mock_photo(label, size, colors):
    img = Image.new("RGB", size, colors[0])
    d = ImageDraw.Draw(img)
    w, h = size
    d.rectangle((20,20,w-20,h-20), outline=colors[1], width=8)
    d.text((40,40), label, fill=colors[1])
    buf = BytesIO()
    img.save(buf, "JPEG", quality=90)
    buf.seek(0)
    return SimpleNamespace(filename=label+".jpg", stream=buf)


data = {
    "group_no":"15",
    "group_name":"부산정책탐험대",
    "members":"왕윤하, 김세연, 오민지, 윤갑선, 왕주용, 윤마루",
    "visit_1_place":"부산근현대역사관",
    "visit_1_insight_1":"역사자원을 체험형 콘텐츠로 연결하는 방식을 참고한다.",
    "visit_1_insight_2":"정읍의 근현대 자원을 시민 참여형 프로그램으로 확장한다.",
    "visit_2_place":"F1963",
    "visit_2_insight_1":"유휴공간을 문화와 상업이 결합된 복합공간으로 전환한다.",
    "visit_2_insight_2":"정읍의 빈 공간에도 전시와 커뮤니티 기능을 결합한다.",
    "visit_3_place":"영화의전당",
    "visit_3_insight_1":"공연과 축제를 통해 야간 체류시간을 늘리는 방식을 참고한다.",
    "visit_3_insight_2":"정읍 문화행사에 반복 방문을 만드는 프로그램을 설계한다.",
    "member_1_name":"왕윤하","member_1_comment":"다른 도시의 정책을 직접 보니 좋았습니다.",
    "member_2_name":"김세연","member_2_comment":"정읍에 적용할 아이디어가 떠올랐습니다.",
    "member_3_name":"오민지","member_3_comment":"조원들과 함께 탐방해서 즐거웠습니다.",
    "member_4_name":"윤갑선","member_4_comment":"공간을 보는 시야가 넓어진 하루였습니다.",
    "member_5_name":"왕주용","member_5_comment":"현장에서 정책 사례를 보니 이해가 쉬웠습니다.",
    "member_6_name":"윤마루","member_6_comment":"다음에도 이런 프로그램에 참여하고 싶습니다.",
}
files = {
    "visit_1_photo": mock_photo("PHOTO 1", (1000,650), ("#bfe3ff","#245b8e")),
    "visit_2_photo": mock_photo("PHOTO 2", (650,1000), ("#ffe0bd","#8e5b24")),
    "visit_3_photo": mock_photo("PHOTO 3", (1200,600), ("#d8f3dc","#2d6a4f")),
}

OUT.write_bytes(build_pdf(data, files).getvalue())
print(OUT)
