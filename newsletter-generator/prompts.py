"""
Storytelling prompts for AI newsletter sections
Each prompt is designed to generate NYT/The Ken quality editorial content
"""

# Section 1: Silicon & Hardware (Chips, GPUs, Infrastructure)
CHIPS_PROMPT = """You are writing for an AI newsletter section about silicon and hardware developments. Write a compelling, story-driven article about the following news:

{articles_summary}

Your article should:
- Start with a captivating hook or scene-setting opening
- Weave a narrative that connects the technical developments to their broader implications
- Explain complex chip/hardware concepts in accessible language
- Include the "why this matters" perspective
- Connect to the larger AI infrastructure story
- End with forward-looking implications

Style: NYT Technology section or The Ken's narrative style
Length: ~500 words
Tone: Informative but engaging, avoiding dry technical jargon

Write the article now:"""

# Section 2: Models & Research (New models, papers, breakthroughs)
MODELS_PROMPT = """You are writing for an AI newsletter section about AI models and research developments. Write a compelling, story-driven article about the following research news:

{articles_summary}

Your article should:
- Open with the significance of these developments in the AI research landscape
- Tell the story of what these models/papers achieve and why it matters
- Explain the technical breakthroughs in a way that's accessible to informed readers
- Connect research to real-world applications
- Highlight the competitive dynamics (which labs, which approaches are winning)
- Discuss implications for the field's direction

Style: NYT Science section or The Ken's analytical narrative
Length: ~500 words
Tone: Curious and exploratory, celebrating innovation while being analytical

Write the article now:"""

# Section 3: Applications & Products (Consumer apps, enterprise tools)
APPLICATIONS_PROMPT = """You are writing for an AI newsletter section about AI applications and products. Write a compelling, story-driven article about the following product/application news:

{articles_summary}

Your article should:
- Start with a real-world use case or user story
- Show how AI is being deployed in practical applications
- Discuss user adoption, business models, and market dynamics
- Highlight what's working and what's not in AI products
- Connect individual products to larger trends in AI deployment
- Consider the user experience and accessibility angle

Style: NYT Business section or The Ken's market analysis
Length: ~500 words
Tone: Pragmatic and user-focused, balancing hype with reality

Write the article now:"""

# Section 4: Policy & Regulation (Laws, ethics, governance)
POLICY_PROMPT = """You are writing for an AI newsletter section about AI policy and regulation. Write a compelling, story-driven article about the following policy/regulatory news:

{articles_summary}

Your article should:
- Frame the regulatory/ethical issue at stake and why it matters now
- Explain the positions of different stakeholders (regulators, companies, advocates)
- Connect specific policy moves to larger questions about AI governance
- Discuss the tension between innovation and regulation
- Highlight international differences in approach
- Consider long-term implications for the industry

Style: NYT Opinion/Analysis or The Ken's investigative approach
Length: ~500 words
Tone: Balanced but not afraid to point out tensions and contradictions

Write the article now:"""

# Section 5: Business & Market (Funding, M&A, strategy)
BUSINESS_PROMPT = """You are writing for an AI newsletter section about AI business and markets. Write a compelling, story-driven article about the following business news:

{articles_summary}

Your article should:
- Lead with the most significant business move and its strategic rationale
- Analyze what these deals/investments reveal about where AI value is concentrating
- Discuss the winners and losers in the current AI economy
- Connect financial moves to technical and product trends
- Consider the sustainability of current business models and valuations
- Look ahead to what these moves signal for the industry

Style: The Ken's business analysis or WSJ Tech section
Length: ~500 words
Tone: Sharp and analytical, following the money and power

Write the article now:"""


def get_prompt_for_section(value_chain_area):
    """Get the appropriate prompt for a value chain area"""
    prompts = {
        'chips': CHIPS_PROMPT,
        'models': MODELS_PROMPT,
        'applications': APPLICATIONS_PROMPT,
        'policy': POLICY_PROMPT,
        'business': BUSINESS_PROMPT
    }
    return prompts.get(value_chain_area, MODELS_PROMPT)


def get_section_title(value_chain_area):
    """Get default section title for a value chain area"""
    titles = {
        'chips': 'Silicon & Infrastructure',
        'models': 'Models & Research',
        'applications': 'Applications & Products',
        'policy': 'Policy & Governance',
        'business': 'Business & Markets'
    }
    return titles.get(value_chain_area, 'AI Updates')


def format_articles_for_prompt(articles):
    """Format a list of articles into a summary for the prompt"""
    formatted = []

    for idx, article in enumerate(articles, 1):
        summary = f"{idx}. {article['title']}\n"

        if article.get('summary'):
            summary += f"   {article['summary'][:200]}...\n"

        if article.get('url'):
            summary += f"   Source: {article.get('source_name', 'Unknown')}\n"

        if article.get('published_at'):
            summary += f"   Date: {article['published_at'].strftime('%B %d, %Y')}\n"

        formatted.append(summary)

    return "\n".join(formatted)
