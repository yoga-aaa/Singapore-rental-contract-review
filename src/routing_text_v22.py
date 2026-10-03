"""Routing/matching aliases only; bound quotations are never rewritten."""
import re

ALIASES=[
    (r'\blessor\b','Landlord'),(r'\blessee\b','Tenant'),
    (r'\bpays back\b','refunds'),(r'\bpay back\b','refund'),
    (r'\breimburse\b(?=.{0,35}\bdeposit\b)','refund'),
    (r'\bno later than\b','within'),(r'\bfollowing\b','after'),
    (r'\b(?:surrender|return) of (?:the )?keys\b','handover'),
    (r'\bfinish\w*\b','complete'),(r'\bbring (?:this |the )?(?:agreement|tenancy) to an end\b','terminate'),
    (r'\b(?:per year|yearly)\b','per annum'),
]


def match_text(text):
    for pattern,replacement in ALIASES: text=re.sub(pattern,replacement,text,flags=re.I)
    return text
