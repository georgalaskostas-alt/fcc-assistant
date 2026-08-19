import asyncio

from app.shift_report import ShiftReportEngine
from app.tag_registry import TagDefinition


class FakeRegistry:
    def list(self):
        return [
            TagDefinition("feed_flow", "Feed Flow", "feed", "TEST.FEED", "web-feed", "m3/h"),
            TagDefinition("reactor_temp", "Reactor Temperature", "reactor", "TEST.RX", "web-rx", "C"),
        ]


class FakeTagService:
    registry = FakeRegistry()

    async def recorded_values(self, key, start_time, end_time, max_count=1000):
        values = [100.0, 110.0] if key == "feed_flow" else [520.0, 524.0]
        return {
            "data": {
                "Items": [
                    {"Timestamp": "2026-08-19T07:00:00Z", "Value": values[0]},
                    {"Timestamp": "2026-08-19T15:00:00Z", "Value": values[1]},
                ]
            }
        }


def test_shift_report_groups_tags_and_summarizes():
    report = asyncio.run(
        ShiftReportEngine(FakeTagService()).generate(
            "2026-08-19T07:00:00Z", "2026-08-19T15:00:00Z"
        )
    )
    assert report["successful_tags"] == 2
    assert report["failed_tags"] == 0
    assert report["groups"]["feed"][0]["summary"]["average"] == 105.0
    assert report["groups"]["reactor"][0]["summary"]["absolute_change"] == 4.0
