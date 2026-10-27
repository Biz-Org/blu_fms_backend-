# -*- coding: utf-8 -*-
{
    "name": "Fire Safety ↔ Community Bridge",
    "version": "18.0.1.0.1",
    "category": "Services",
    "summary": "Publish Community announcements when Fire & Safety mock drills are scheduled",
    "description": """
Bridge between Fire & Safety Management and Community & Communication.

When a mock drill is created with selected participants, publishes a Safety
announcement targeted at those participants' resident profiles so it appears
on the Community Announcements tab.
    """,
    "author": "FMS",
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "depends": [
        "fire_safety_management",
        "community_communication",
    ],
    "data": [],
}
