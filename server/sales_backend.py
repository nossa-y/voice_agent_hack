#
# ColdLoop Sales Agent — Mock backend data
#
# Swap these dicts with real API calls when moving beyond the hackathon demo.
# Prospect personas are selected randomly per call to keep demos varied.
#

"""Mock backend data for the ColdLoop sales agent demo.

This file exports product information, competitor comparisons, and prospect
personas used by the sales agent bot. All data is fictional and designed
for a compelling hackathon demo.

Edit PROSPECT_PERSONAS to add or modify the prospects the agent will call.
Edit SYNCFLOW_PRODUCT to change what the agent knows about the product.
Edit COMPETITORS to update competitive positioning.
"""

SYNCFLOW_PRODUCT = {
    "name": "ColdLoop",
    "tagline": "Data pipelines that build themselves",
    "description": (
        "ColdLoop is a data pipeline platform for mid-market ops teams. "
        "Connect any source to any destination, transform data with plain "
        "English rules, and monitor pipeline health from one dashboard. "
        "No engineering backlog required."
    ),
    "features": {
        "connectors": {
            "name": "Universal Connectors",
            "detail": (
                "Pre-built connectors for over 200 sources and destinations "
                "including Salesforce, HubSpot, Snowflake, BigQuery, Postgres, "
                "Stripe, NetSuite, and Workday. New connectors ship every two weeks."
            ),
            "differentiator": (
                "Most competitors top out at 50 to 80 connectors. "
                "We have 200 plus and add more every sprint."
            ),
        },
        "transformations": {
            "name": "Plain English Transforms",
            "detail": (
                "Write transformation rules in plain English. ColdLoop's AI "
                "translates them into optimized SQL. No dbt, no data engineering "
                "hire required."
            ),
            "differentiator": (
                "Fivetran and Airbyte still require dbt or custom code for "
                "transforms. We handle it natively."
            ),
        },
        "monitoring": {
            "name": "Pipeline Health Dashboard",
            "detail": (
                "Real-time monitoring with anomaly detection. Get Slack or email "
                "alerts when row counts drop, schemas change, or latency spikes. "
                "Full data lineage graph."
            ),
            "differentiator": (
                "Competitors charge extra for observability. "
                "Ours is built in at every tier."
            ),
        },
        "security": {
            "name": "Enterprise Security",
            "detail": (
                "SOC 2 Type II certified. Data encrypted in transit and at rest. "
                "Role-based access control, SSO, and audit logs. Your data never "
                "touches our servers in the managed VPC option."
            ),
            "differentiator": (
                "We offer a managed VPC deployment where data never leaves your "
                "cloud. Most competitors are SaaS-only."
            ),
        },
        "speed": {
            "name": "Real-Time Sync",
            "detail": (
                "Sub-minute sync latency with CDC support. Batch or streaming, "
                "your choice per pipeline. Handles up to 10 billion rows per day."
            ),
            "differentiator": (
                "Fivetran's standard tier is 60-minute sync intervals. "
                "Our base plan starts at sub-minute."
            ),
        },
    },
    "pricing": {
        "starter": {
            "name": "Starter",
            "price": "$500/month",
            "details": (
                "Up to 5 million rows per month, 20 connectors, email support. "
                "Good for small teams getting started."
            ),
        },
        "growth": {
            "name": "Growth",
            "price": "$2,000/month",
            "details": (
                "Up to 50 million rows per month, unlimited connectors, plain "
                "English transforms, Slack support, SSO. Most popular for "
                "mid-market ops teams."
            ),
        },
        "enterprise": {
            "name": "Enterprise",
            "price": "Custom pricing, typically $5,000 to $15,000/month",
            "details": (
                "Unlimited rows, managed VPC deployment, dedicated support "
                "engineer, SLA guarantees, custom connectors, data lineage. "
                "For teams with strict compliance needs."
            ),
        },
    },
    "customers_count": "400+",
    "notable_segments": (
        "mid-market ops teams, RevOps, finance ops, "
        "data teams without dedicated engineers"
    ),
}

COMPETITORS = {
    "fivetran": {
        "name": "Fivetran",
        "our_advantages": [
            "We include transformations natively; Fivetran requires dbt as a separate tool and cost",
            "Sub-minute sync on our base plan versus 60-minute intervals on Fivetran's standard tier",
            "Our monitoring and anomaly detection is built in; Fivetran charges extra for their observability add-on",
            "We're typically 30 to 40 percent less expensive at comparable volumes",
        ],
        "their_strengths": [
            "Larger brand name and more enterprise references",
            "Slightly larger connector library, though we're closing the gap fast",
        ],
        "talk_track": (
            "Fivetran's a solid product, but their architecture was built for batch. "
            "If your team needs faster sync or doesn't want to manage a separate dbt "
            "layer, that's exactly where we shine."
        ),
    },
    "airbyte": {
        "name": "Airbyte",
        "our_advantages": [
            "Fully managed with no infrastructure to maintain; Airbyte's open-source version requires self-hosting",
            "Plain English transforms built in; Airbyte has no native transformation layer",
            "Enterprise support with SLAs; Airbyte Cloud support is still maturing",
        ],
        "their_strengths": [
            "Open-source option appeals to engineering-heavy teams",
            "Lower entry cost if you self-host and have the engineering bandwidth",
        ],
        "talk_track": (
            "Airbyte's great if you have engineers who want to self-host and maintain "
            "pipelines. For ops teams who want it to just work without a DevOps hire, "
            "ColdLoop is the better fit."
        ),
    },
    "stitch": {
        "name": "Stitch",
        "our_advantages": [
            "Much broader connector library, 200 plus versus Stitch's roughly 130",
            "Real-time CDC sync; Stitch only supports batch replication",
            "Active development and support; Stitch has had limited updates since the Talend acquisition",
        ],
        "their_strengths": [
            "Simple pricing model",
            "Familiar to teams already using Talend's ecosystem",
        ],
        "talk_track": (
            "Stitch hasn't seen much investment since Talend acquired them. If you're "
            "evaluating options, you'll find ColdLoop is more actively developed with "
            "better real-time capabilities."
        ),
    },
}

PROSPECT_PERSONAS = [
    {
        "id": "prospect_1",
        "name": "Sarah Chen",
        "title": "VP of Revenue Operations",
        "company": "Meridian Analytics",
        "company_size": "350 employees",
        "industry": "B2B SaaS",
        "pain_points": [
            "Data team is bottlenecked; RevOps requests sit in the engineering backlog for weeks",
            "Currently using spreadsheet exports to move data between Salesforce and their data warehouse",
            "Pipeline breaks go undetected until someone notices stale dashboards",
        ],
        "current_tools": "Salesforce, HubSpot, Snowflake, manual CSV exports",
        "budget_authority": True,
        "trigger_event": "Just hired a new CRO who wants real-time pipeline visibility within 90 days",
        "objection_tendency": "Will ask about implementation timeline and resources needed",
    },
    {
        "id": "prospect_2",
        "name": "Marcus Johnson",
        "title": "Head of Data",
        "company": "GreenPath Logistics",
        "company_size": "800 employees",
        "industry": "Logistics and Supply Chain",
        "pain_points": [
            "Running 40 plus Airbyte pipelines that keep breaking when schemas change",
            "Spending 20 hours a week on pipeline maintenance instead of analysis",
            "CEO wants a unified dashboard but data is scattered across 6 systems",
        ],
        "current_tools": "Airbyte (self-hosted), PostgreSQL, Metabase, custom Python scripts",
        "budget_authority": False,
        "trigger_event": "Their lead data engineer just quit, and nobody else knows how to maintain the Airbyte setup",
        "objection_tendency": "Will push back on cost and want to compare with fixing their current Airbyte setup",
    },
    {
        "id": "prospect_3",
        "name": "Priya Patel",
        "title": "Director of Finance Operations",
        "company": "NovaBridge Financial",
        "company_size": "200 employees",
        "industry": "Financial Services",
        "pain_points": [
            "Month-end close takes 8 days because data from NetSuite, Stripe, and their billing system has to be manually reconciled",
            "Compliance team needs audit trails for all data movement, which they currently track in spreadsheets",
            "No visibility into when data was last synced or if numbers in reports are current",
        ],
        "current_tools": "NetSuite, Stripe, QuickBooks, Google Sheets, Fivetran (considering switching)",
        "budget_authority": True,
        "trigger_event": "Failed an internal audit because they couldn't prove data lineage for a financial report",
        "objection_tendency": "Will focus on security, compliance, and SOC 2 requirements",
    },
    {
        "id": "prospect_4",
        "name": "David Kim",
        "title": "Operations Manager",
        "company": "Atlas Health Tech",
        "company_size": "150 employees",
        "industry": "Health Tech",
        "pain_points": [
            "Growing fast but ops processes don't scale; everything runs on tribal knowledge and manual steps",
            "Sales and customer success use different data, leading to conflicting reports to leadership",
            "Evaluated Fivetran but the quote came back at three times their budget",
        ],
        "current_tools": "HubSpot, Intercom, PostgreSQL, Google Sheets",
        "budget_authority": True,
        "trigger_event": "Series B funding closed last month; board wants operational metrics dashboards by next quarter",
        "objection_tendency": "Price-sensitive, will want to see ROI math and a pilot program",
    },
]
