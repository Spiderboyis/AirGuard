# Demo script (3 minutes)

There is no live demo at judging; the video is what judges see. Record from a frozen snapshot so the
numbers match `docs/headline.json`.

## Before recording

```bash
make db-start && make forecast        # fresh data
make snapshot                         # freezes it; prints the snapshot path
# in .env.local: DEMO_SNAPSHOT=backend/snapshots/<stamp>.json  (then restart the API)
make dev
```

Open the app in a clean browser profile at 1440×900, light theme. Warm the model once
(`curl -X POST localhost:8000/agent/chat ...`) so the first answer isn't a cold start.

## Script

| Time | Screen | Say |
| --- | --- | --- |
| 0:00 | Landing page, ride-window chart | "Riya cycles from Hauz Khas to North Campus. Delhi's AQI apps tell her the air is bad. None tell her what to do about it." Drag the "Try another departure" slider: "This curve is the forecast along her route; the box is her ride. Slide it, and you can see what leaving later does." |
| 0:15 | Onboarding: cycle → sensitive → limits | "She sets up once: she cycles, she has asthma, and she'll accept 15 extra minutes on the road and up to two hours' wait. Look: a 30-minute wait now needs at least a 22% cut to be worth it." |
| 0:40 | Planner: plan the trip | "AirGuard pulls real routes and scores every 200 metres against the PM2.5 forecast for the minute she'd be there." |
| 0:55 | Recommendation + map toggle | Read the headline from `docs/headline.json`: "+X minutes, −Y% exposure." Toggle "leaving now / leaving later" on the map. |
| 1:15 | Departure chart, route cards | "Every option, every 15 minutes. And every number has a confidence: here it's medium, because the nearest monitor is 2 km away." |
| 1:35 | Ask AirGuard: "Why not just leave now?" | "The assistant runs on the Strands Agents SDK. Watch the tool calls: it reads the saved analysis, and every number it writes is checked against what the tools returned." Open a tool call. |
| 2:05 | Evidence page | "We tested the forecast on two weeks it never saw, against the last reading, the usual level for that hour, and the CAMS global model." Point at the +1 h and +6 h rows. "And when CPCB's feed goes down, as it did this week, the model still estimates every station." |
| 2:30 | Method page / map of estimated stations | "Everything's stated: mode factors, bands, the decision rule. It compares options within one way of travelling and gives guidance, not medical advice." |
| 2:45 | Architecture slide | "Strands Agents for the assistant; on AWS it's Bedrock, Lambda, EventBridge and S3. Next: school-run mode, more cities, and a public API." |

## Backup

Record a second, unedited take. If the language model misbehaves, the assistant falls back to the verified
explanation and says so; that's fine to show.
