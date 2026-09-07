"""固定采样时间轴的边界和只读语义测试。"""

from __future__ import annotations

import unittest

from replay.timeline import ReplayFrame, ReplayTimeline


def frame(time, **values):
    return ReplayFrame(time=time, **values)


class ReplayTrailTest(unittest.TestCase):
    def test_trail_frames_are_rebuilt_from_time_window(self):
        timeline = ReplayTimeline()
        timeline.record_initial(frame(0.0, theta=0.0, omega=0.0))
        timeline.record_sample(frame(0.2, theta=0.2, omega=0.5), force=True)
        timeline.record_sample(frame(1.1, theta=1.1, omega=0.5), force=True)
        selected = timeline.trail_frames(1.1, lifetime=0.8, speed_threshold=0.03)
        self.assertEqual([item.time for item in selected], [1.1])


class ReplayTimelineTest(unittest.TestCase):
    def test_fixed_sampling_drops_intermediate_live_frames(self):
        timeline = ReplayTimeline(sample_interval=0.1)
        timeline.record_initial(frame(0.0, theta=0.0))
        self.assertFalse(timeline.record_sample(frame(0.04, theta=4.0)))
        self.assertTrue(timeline.record_sample(frame(0.11, theta=11.0)))
        self.assertFalse(timeline.record_sample(frame(0.15, theta=15.0)))
        self.assertEqual([item.time for item in timeline.frames], [0.0, 0.11])

    def test_collision_is_instant_and_post_state_continues(self):
        timeline = ReplayTimeline(sample_interval=0.1)
        timeline.record_initial(frame(0.0, theta=0.0, omega=1.0))
        timeline.record_sample(frame(0.2, theta=0.2, omega=2.0), force=True)
        timeline.record_collision(
            frame(0.2, phase="swinging", theta=0.2, omega=2.0,
                  ball_v=0.0, total_energy=5.0),
            frame(0.2, phase="after", theta=0.2, omega=-1.0,
                  ball_v=3.0, total_energy=4.0),
        )
        timeline.record_sample(frame(0.3, phase="after", theta=0.1, omega=-0.8,
                                     ball_v=3.2, total_energy=3.9), force=True)

        self.assertEqual(timeline.collision_count, 1)
        before = timeline.frame_at(0.2, side="before")
        after = timeline.frame_at(0.2, side="after")
        self.assertEqual(before.event, "collision_before")
        self.assertEqual(after.event, "collision_after")
        self.assertEqual(before.collision_id, after.collision_id)
        self.assertAlmostEqual(after.time, 0.2)
        self.assertEqual(before.time, after.time)
        self.assertIsNone(timeline.frame_at(0.275, side="after").event)
        self.assertAlmostEqual(timeline.collision_intensity_at(0.2), 1.0)
        self.assertLess(timeline.collision_intensity_at(0.275), 1.0)
        self.assertEqual(timeline.collision_window_at(0.1), None)
        self.assertEqual(timeline.frame_at(0.2, side="before").ball_v, 0.0)
        self.assertAlmostEqual(timeline.frame_at(0.275, side="after").ball_v,
                               3.15)
        self.assertAlmostEqual(timeline.frame_at(0.275, side="after").theta,
                               0.125)
        self.assertIsNone(timeline.collision_window_at(0.275))

    def test_normal_frames_interpolate_and_post_collision_stays_continuous(self):
        timeline = ReplayTimeline(sample_interval=0.1)
        timeline.record_initial(frame(0.0, theta=0.0, omega=0.0))
        timeline.record_sample(frame(0.1, theta=1.0, omega=2.0), force=True)
        middle = timeline.frame_at(0.05)
        self.assertAlmostEqual(middle.theta, 0.5)
        self.assertAlmostEqual(middle.omega, 1.0)

        timeline.record_collision(
            frame(0.2, theta=1.0, omega=2.0),
            frame(0.2, theta=1.0, omega=-1.0),
        )
        timeline.record_sample(frame(0.3, theta=0.8, omega=-0.5), force=True)
        post = timeline.frame_at(0.25)
        self.assertAlmostEqual(post.omega, -0.75)
        self.assertIsNone(post.event)

        after_window = timeline.frame_at(0.4)
        self.assertAlmostEqual(after_window.omega, -0.5)

    def test_seek_is_read_only_and_go_live_selects_after_frame(self):
        timeline = ReplayTimeline()
        timeline.record_initial(frame(0.0, theta=2.0))
        timeline.record_sample(frame(0.1, theta=3.0), force=True)
        original = tuple(timeline.frames)
        selected = timeline.seek(0.05)
        self.assertAlmostEqual(selected.theta, 2.5)
        self.assertEqual(tuple(timeline.frames), original)
        self.assertFalse(timeline.live)
        live = timeline.go_live()
        self.assertEqual(live.theta, 3.0)
        self.assertTrue(timeline.live)


if __name__ == "__main__":
    unittest.main()
