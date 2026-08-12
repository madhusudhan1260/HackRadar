"""Seed collector — a realistic offline dataset.

Every deadline is expressed as an offset from today, so the "Deadlines"
board always has something in Today / This Week / Next Week no matter when
you run the project. Use it for development, demos and tests; the live
collectors add real listings on top.
"""
from __future__ import annotations

from datetime import date, timedelta

from .base import Collector, RawHackathon

# (title, org, days_until_deadline, duration, location, prize, tags, description)
_SEED: list[dict] = [
    dict(
        title="Arm AI Optimization Challenge",
        organizer="Arm",
        due=3, span=21, location="Online", prize="$8,000",
        tags=["Python", "AI", "Machine Learning", "Edge Computing"],
        team="team 1-4",
        desc="Optimise machine learning inference for Arm-based edge devices. "
             "Submissions are judged on latency, accuracy and power efficiency.",
    ),
    dict(
        title="Smart India Hackathon - Software Edition",
        organizer="Ministry of Education, Govt. of India",
        due=0, span=2, location="Bengaluru, India", prize="₹1,00,000",
        tags=["Python", "Web Development", "Open Innovation"],
        team="team 6-6", student=True,
        desc="India's largest nationwide hackathon for students. Solve real problem "
             "statements submitted by government ministries and industry partners.",
    ),
    dict(
        title="IIT Bombay ML Challenge",
        organizer="IIT Bombay Analytics Club",
        due=1, span=14, location="Mumbai, India", prize="₹2,50,000",
        tags=["Machine Learning", "Python", "Deep Learning", "PyTorch"],
        team="team 1-3", student=True,
        desc="A two-week machine learning competition on real-world tabular and "
             "vision datasets. Open to all college students in India.",
    ),
    dict(
        title="QuantStorm Trading Hackathon",
        organizer="QuantStorm Labs",
        due=4, span=7, location="Online", prize="$15,000",
        tags=["Python", "Quantitative Finance", "Data Science"],
        team="team 1-2",
        desc="Build and backtest a systematic trading strategy. Top strategies by "
             "risk-adjusted return share the prize pool.",
    ),
    dict(
        title="Microsoft Azure AI Challenge",
        organizer="Microsoft",
        due=11, span=30, location="Online", prize="$25,000",
        tags=["Azure", "AI", "Cloud", "LLM", "Python"],
        team="team 1-5",
        desc="Build a generative AI application on Azure AI Foundry. Free Azure "
             "credits provided to every registered team.",
    ),
    dict(
        title="Google Cloud Gen AI Hackathon",
        organizer="Google Cloud",
        due=13, span=28, location="Online", prize="$30,000",
        tags=["GCP", "Cloud", "Generative AI", "LLM", "Python"],
        team="team 1-4",
        desc="Use Vertex AI and Gemini models to build an application that solves a "
             "measurable business problem.",
    ),
    dict(
        title="HackTheBox University CTF",
        organizer="Hack The Box",
        due=6, span=3, location="Online", prize="$10,000",
        tags=["Cybersecurity", "CTF", "Python", "Reverse Engineering"],
        team="team 1-10", student=True,
        desc="A jeopardy-style capture the flag for university teams. Categories "
             "include web exploitation, pwn, crypto, forensics and reversing.",
    ),
    dict(
        title="AWS DeepRacer Student League",
        organizer="Amazon Web Services",
        due=18, span=45, location="Online", prize="$20,000",
        tags=["AWS", "Cloud", "Reinforcement Learning", "Python"],
        team="team 1-1", student=True,
        desc="Train a reinforcement learning model to race an autonomous 1/18th "
             "scale car around a virtual track.",
    ),
    dict(
        title="Devfolio Web3 Buildathon",
        organizer="Devfolio",
        due=9, span=21, location="Online", prize="₹8,00,000",
        tags=["Blockchain", "Solidity", "Web3", "Ethereum"],
        team="team 1-4",
        desc="Ship a decentralised application on any EVM chain. Mentorship from "
             "protocol teams and sponsor bounties on top of the main pool.",
    ),
    dict(
        title="Flipkart GRiD - Software Development Track",
        organizer="Flipkart",
        due=15, span=60, location="Bengaluru, India", prize="₹5,00,000",
        tags=["Java", "System Design", "Backend", "SQL"],
        team="team 2-3", student=True,
        desc="Flipkart's flagship engineering campus challenge. Three rounds, "
             "ending with an on-site finale and pre-placement interviews.",
    ),
    dict(
        title="NASA Space Apps Challenge",
        organizer="NASA",
        due=22, span=2, location="Hyderabad, India", prize="$0",
        tags=["Python", "Data Science", "Open Data", "Space"],
        team="team 1-6",
        desc="A 48-hour international hackathon using open NASA earth and space "
             "science data. Local host sites in 150+ countries.",
    ),
    dict(
        title="HackerEarth Machine Learning Sprint",
        organizer="HackerEarth",
        due=5, span=10, location="Online", prize="₹75,000",
        tags=["Machine Learning", "Python", "Data Science"],
        team="team 1-1",
        desc="A ten-day solo ML sprint on a private leaderboard dataset. Weekly "
             "sprints are free to enter.",
    ),
    dict(
        title="Cisco Secure Code Challenge",
        organizer="Cisco",
        due=8, span=14, location="Online", prize="$12,000",
        tags=["Cybersecurity", "Python", "AppSec", "DevOps"],
        team="team 1-3",
        desc="Find and fix vulnerabilities in a deliberately insecure microservice "
             "stack. Scored on remediation quality, not just detection.",
    ),
    dict(
        title="Flutter India App Jam",
        organizer="Google Developer Groups India",
        due=12, span=14, location="Online", prize="₹1,50,000",
        tags=["Flutter", "Dart", "Mobile", "Android"],
        team="team 1-4", student=True,
        desc="Build a cross-platform Flutter app that works offline-first for "
             "low-connectivity regions.",
    ),
    dict(
        title="ETHIndia Fellowship Hack",
        organizer="ETHIndia",
        due=25, span=3, location="Bengaluru, India", prize="₹20,00,000",
        tags=["Blockchain", "Solidity", "Web3"],
        team="team 2-4",
        desc="Asia's largest Ethereum hackathon. 36 hours on-site, travel "
             "reimbursement for shortlisted teams.",
    ),
    dict(
        title="Kaggle Community Prediction Competition",
        organizer="Kaggle",
        due=30, span=60, location="Online", prize="$50,000",
        tags=["Machine Learning", "Python", "Data Science", "Deep Learning"],
        team="team 1-5",
        desc="A featured prediction competition on a large real-world dataset with "
             "a public and private leaderboard.",
    ),
    dict(
        title="Adobe India Hackathon - Design & Build",
        organizer="Adobe",
        due=19, span=21, location="Noida, India", prize="₹4,00,000",
        tags=["UI/UX", "React", "JavaScript", "Design"],
        team="team 2-4", student=True,
        desc="Design and build a creative tool extension. Judged equally on "
             "interface craft and engineering quality.",
    ),
    dict(
        title="Open Source Contribution Sprint",
        organizer="FOSS United",
        due=7, span=30, location="Online", prize="₹50,000",
        tags=["Open Source", "Python", "JavaScript", "Git"],
        team="team 1-1", student=True,
        desc="Contribute merged pull requests to participating open source Indian "
             "projects. Ranked by impact, not raw PR count.",
    ),
    dict(
        title="IoT for Agriculture Challenge",
        organizer="Bosch India",
        due=16, span=45, location="Pune, India", prize="₹3,00,000",
        tags=["IoT", "Arduino", "Embedded", "C++", "Sustainability"],
        team="team 2-5",
        desc="Prototype a low-cost sensor system for smallholder farms. Hardware "
             "kits shipped to shortlisted teams.",
    ),
    dict(
        title="Global Game Jam Online",
        organizer="Global Game Jam",
        due=27, span=3, location="Online", prize="$0",
        tags=["Game Development", "Unity", "C#"],
        team="team 1-6",
        desc="48 hours to build a game around a surprise theme announced at the "
             "start. No entry fee, all skill levels.",
    ),
    dict(
        title="Healthcare AI Datathon",
        organizer="AIIMS x IIT Delhi",
        due=20, span=14, location="New Delhi, India", prize="₹2,00,000",
        tags=["Machine Learning", "Healthcare", "Python", "Computer Vision"],
        team="team 2-4", student=True,
        desc="Build diagnostic models on de-identified clinical imaging data under "
             "supervised access.",
    ),
    dict(
        title="Cloud Native Kubernetes Hack Day",
        organizer="CNCF",
        due=10, span=1, location="Online", prize="$5,000",
        tags=["Kubernetes", "Docker", "Cloud", "Go", "DevOps"],
        team="team 1-3",
        desc="A single-day hack on the cloud native stack: operators, observability "
             "and platform tooling.",
    ),
    dict(
        title="Barclays Fintech Innovation Cup",
        organizer="Barclays",
        due=24, span=30, location="Pune, India", prize="₹6,00,000",
        tags=["Fintech", "Java", "Backend", "SQL", "Payments"],
        team="team 3-4", student=True,
        desc="Reimagine a retail banking journey. Finalists present to the Barclays "
             "India technology leadership team.",
    ),
    dict(
        title="Climate Tech Hack Europe",
        organizer="ClimateHack EU",
        due=17, span=21, location="Berlin, Germany", prize="€20,000",
        tags=["Sustainability", "Python", "Data Science", "Cloud"],
        team="team 1-4",
        desc="Use open energy grid data to cut carbon intensity. Remote "
             "participation supported for international teams.",
    ),
]


class SeedCollector(Collector):
    name = "seed"
    access_note = "Bundled offline sample data — always safe to run."

    def fetch(self, limit: int = 200) -> list[RawHackathon]:
        today = date.today()
        records: list[RawHackathon] = []

        for index, item in enumerate(_SEED[:limit]):
            deadline = today + timedelta(days=item["due"])
            start = deadline + timedelta(days=2)
            end = start + timedelta(days=item["span"])
            location = item["location"]
            desc = item["desc"]
            # Only add the audience hint when the copy doesn't already say it.
            if item.get("student") and "student" not in desc.lower():
                desc += " Open to college students."

            records.append(
                RawHackathon(
                    source=self.name,
                    source_id=f"seed-{index:03d}",
                    url=f"https://example.com/hackathons/{_slug(item['title'])}",
                    title=item["title"],
                    description=desc,
                    organizer=item["organizer"],
                    deadline=deadline,
                    start_date=start,
                    end_date=end,
                    location=location,
                    mode_hint=location,
                    prize_text=item["prize"],
                    prize_currency="INR" if "₹" in item["prize"] else "USD",
                    fee_text="Free entry",
                    team_text=item.get("team", "team 1-4"),
                    tags=item["tags"],
                    raw={"seed": True},
                )
            )
        return records


def _slug(value: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in value.lower()).strip("-")
