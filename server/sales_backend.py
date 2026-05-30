#
# Getcleed Sales Agent - Backend data
#
# Real product data from getcleed.com. Prospect personas are fictional
# but represent the actual target market.
#

"""Backend data for the Getcleed sales agent.

Getcleed is an AI-powered B2B lead scoring and outreach intelligence platform.
It monitors buying signals 24/7, scores prospects by timing and fit, and
generates personalized outreach automatically.
"""

SYNCFLOW_PRODUCT = {
    "name": "Getcleed",
    "tagline": "Find leads at the right timing, not just the right fit",
    "description": (
        "Getcleed is an AI-powered prospecting platform that monitors the market "
        "24/7 for buying signals - funding rounds, hiring spikes, leadership changes, "
        "competitor mentions, product launches. It scores every account by fit, timing, "
        "and urgency, then generates personalized outreach with a clear reason to reach out. "
        "Your team stops cold-blasting lists and starts contacting people who are actually "
        "ready to buy."
    ),
    "features": {
        "signals": {
            "name": "Live Buying Signals",
            "detail": (
                "Tracks over 100 buying signals in real time: funding rounds, hiring spikes, "
                "LinkedIn activity, leadership changes, competitor mentions, product launches, "
                "tech stack changes. Runs 24/7 even when your team is offline."
            ),
            "differentiator": (
                "Most tools give you a static list. We tell you WHO is ready to buy "
                "and WHY right now. Timing is everything in outreach."
            ),
        },
        "scoring": {
            "name": "Signal-Based Lead Scoring",
            "detail": (
                "Every prospect gets scored on four dimensions: fit, timing, relevance, "
                "and urgency. A company that just raised Series B and is hiring 3 SDRs "
                "scores higher than one that's been quiet for 6 months."
            ),
            "differentiator": (
                "Traditional lead scoring uses firmographics. We score on real-time "
                "market behavior. That's why our leads convert at 3x the rate of cold lists."
            ),
        },
        "outreach": {
            "name": "AI-Generated Outreach",
            "detail": (
                "For every warm lead, Getcleed generates a personalized first email "
                "with a specific reason to reach out. Not generic templates - each "
                "message references the actual signal that triggered it."
            ),
            "differentiator": (
                "Apollo and ZoomInfo give you contact data. We give you contact data "
                "plus the reason to reach out plus a draft message. That's the whole workflow."
            ),
        },
        "workflow": {
            "name": "Team Workflow",
            "detail": (
                "Approve, edit, assign, or sync opportunities to your CRM. "
                "Your team reviews AI-generated outreach before it goes out. "
                "Full control, zero manual research."
            ),
            "differentiator": (
                "We're not an autopilot that spams. Your team stays in control. "
                "The AI does the research, your reps make the calls."
            ),
        },
        "enrichment": {
            "name": "Contact Enrichment",
            "detail": (
                "Automatically enriches every lead with verified emails, LinkedIn "
                "profiles, company data, tech stack, and recent activity. "
                "No more bouncing emails or outdated contacts."
            ),
            "differentiator": (
                "Enrichment is included in every plan. Competitors charge per lookup "
                "or require a separate data provider subscription."
            ),
        },
    },
    "pricing": {
        "pro": {
            "name": "Pro",
            "price": "$99/month",
            "details": (
                "Up to 1,000 leads analyzed per month, unlimited warm lead discovery, "
                "AI-powered emails, contact enrichment, CRM integrations. "
                "7-day free trial, no credit card required."
            ),
        },
        "max": {
            "name": "Max",
            "price": "Custom pricing for teams",
            "details": (
                "Unlimited leads, advanced signal customization, team seats, "
                "dedicated support, custom integrations. For growth teams "
                "and agencies running high-volume outreach."
            ),
        },
    },
    "customers_count": "Growing fast",
    "notable_segments": (
        "B2B sales teams, founders doing their own outreach, SDR teams, "
        "growth agencies, anyone tired of cold list grinding"
    ),
}

COMPETITORS = {
    "apollo": {
        "name": "Apollo",
        "our_advantages": [
            "We surface leads based on real-time buying signals, not just static filters",
            "Every lead comes with a reason to reach out and a personalized draft email",
            "Signal-based scoring means your team contacts people at the right moment, not randomly",
            "At 99 dollars a month we're cheaper than Apollo's comparable plans",
        ],
        "their_strengths": [
            "Massive contact database with hundreds of millions of records",
            "Well-known brand with a large user base",
        ],
        "talk_track": (
            "Apollo gives you a huge database and lets you filter it. That's useful, but "
            "it's still cold outreach. Getcleed tells you who's actually showing buying "
            "intent right now and why. The conversion difference is night and day."
        ),
    },
    "zoominfo": {
        "name": "ZoomInfo",
        "our_advantages": [
            "Fraction of the cost. ZoomInfo starts at thousands per month, we're 99 dollars",
            "We include the outreach intelligence, not just the contact data",
            "Real-time signals versus quarterly-updated firmographic data",
            "No long-term contract required. Month to month.",
        ],
        "their_strengths": [
            "Deepest enterprise contact database in the market",
            "Intent data partnerships and technographic data",
        ],
        "talk_track": (
            "ZoomInfo is the gold standard for contact data, but it costs 10x what we do "
            "and still doesn't tell you WHEN to reach out. Most teams are overpaying for "
            "data they don't fully use. Getcleed gives you the signal plus the outreach."
        ),
    },
    "linkedin sales navigator": {
        "name": "LinkedIn Sales Navigator",
        "our_advantages": [
            "Automated signal monitoring versus manual searching and scrolling",
            "AI-generated outreach drafts versus writing every message yourself",
            "Tracks signals beyond LinkedIn: funding, hiring, tech changes, competitor activity",
            "Lead scoring that combines all signals, not just LinkedIn activity",
        ],
        "their_strengths": [
            "Direct access to the LinkedIn network and InMail",
            "Real-time LinkedIn activity and engagement data",
        ],
        "talk_track": (
            "Sales Nav is great for manual prospecting, but it's a lot of scrolling "
            "and guesswork. Getcleed automates the signal detection and tells you "
            "exactly who to contact and what to say. Your reps spend time selling, "
            "not researching."
        ),
    },
    "clay": {
        "name": "Clay",
        "our_advantages": [
            "No-code setup in minutes versus Clay's complex workflow builder",
            "Built-in signal monitoring versus having to configure data sources yourself",
            "AI outreach generation included versus needing separate AI tools",
            "Simpler pricing, no per-row credits to manage",
        ],
        "their_strengths": [
            "Extremely flexible data enrichment workflows",
            "Power-user tool for teams with technical GTM ops",
        ],
        "talk_track": (
            "Clay is powerful if you have someone who loves building workflows. "
            "Getcleed is for teams who want results without the setup. "
            "Plug in your ICP, and we start finding warm leads immediately."
        ),
    },
}

PROSPECT_PERSONAS = [
    {
        "id": "prospect_1",
        "name": "Jake Morrison",
        "title": "VP of Sales",
        "company": "Packsmith",
        "company_size": "120 employees",
        "industry": "E-commerce Fulfillment Software",
        "pain_points": [
            "SDR team is burning through cold lists with under 2% reply rates",
            "Reps spend 3 hours a day researching before they can even write an email",
            "No way to know which accounts are actually in-market right now",
        ],
        "current_tools": "Apollo, Salesforce, Outreach",
        "budget_authority": True,
        "trigger_event": "Just missed Q1 pipeline target by 30%, board is asking hard questions",
        "objection_tendency": "Will ask about data accuracy and integration with existing stack",
    },
    {
        "id": "prospect_2",
        "name": "Lisa Tran",
        "title": "Head of Growth",
        "company": "Ridgewell",
        "company_size": "45 employees",
        "industry": "Supply Chain Software",
        "pain_points": [
            "Founder-led sales is hitting a ceiling, needs to scale outbound without hiring 5 SDRs",
            "Tried ZoomInfo but the contract was 20K a year and most leads were stale",
            "Spending too much time on LinkedIn manually looking for prospects",
        ],
        "current_tools": "LinkedIn Sales Navigator, HubSpot, Google Sheets",
        "budget_authority": True,
        "trigger_event": "Just closed Series A, need to show 3x pipeline growth to investors",
        "objection_tendency": "Price-conscious, will compare with doing it manually or hiring an SDR",
    },
    {
        "id": "prospect_3",
        "name": "Dan Cooper",
        "title": "Director of Business Development",
        "company": "Folio Systems",
        "company_size": "300 employees",
        "industry": "RevOps Software",
        "pain_points": [
            "Outbound emails feel generic and get ignored. Reply rates dropped from 8% to 2% this year",
            "No system to track which target accounts are showing buying signals",
            "BDRs waste time on accounts that aren't ready, miss the ones that are",
        ],
        "current_tools": "Salesforce, Outreach, Clay (trying it out)",
        "budget_authority": False,
        "trigger_event": "CEO mandate to double new client acquisition this year with same headcount",
        "objection_tendency": "Will want proof of ROI and case studies from similar companies",
    },
    {
        "id": "prospect_4",
        "name": "Maria Santos",
        "title": "SDR Manager",
        "company": "Trellus",
        "company_size": "200 employees",
        "industry": "Sales Enablement",
        "pain_points": [
            "Team of 6 SDRs books maybe 15 meetings a month total. Target is 40",
            "Using Apollo but reps just blast the same sequences to everyone",
            "No way to prioritize which accounts to hit first each morning",
        ],
        "current_tools": "Apollo, Salesloft, Salesforce",
        "budget_authority": True,
        "trigger_event": "Two SDRs just quit, need to hit the same number with 4 people",
        "objection_tendency": "Will ask how this is different from Apollo's buying signals feature",
    },
]
