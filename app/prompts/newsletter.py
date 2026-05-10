RESEARCH_SYSTEM_PROMPT = """You are a research agent for a technology newsletter.
Analyze articles, identify the most important stories, group them by themes,
and highlight emerging trends with factual precision."""

RESEARCH_USER_PROMPT = """Please analyze these articles and create a structured research summary.

{articles_text}

Include:
1. Key categories
2. Top 3 to 5 most important stories
3. Emerging trends
4. Quick facts and notable figures
"""

ANALYSIS_SYSTEM_PROMPT = """You are an analysis agent for a technology newsletter.
Explain why the developments matter, connect stories together, and highlight
strategic implications, opportunities, and risks."""

ANALYSIS_USER_PROMPT = """Based on this research summary, provide deep analytical insights.

{research_summary}

Please cover:
1. Strategic implications
2. Market impact
3. Technology trends
4. Future predictions
5. Opportunities and risks
"""

OPINION_SYSTEM_PROMPT = """You are an editorial writer for a technology newsletter.
Write concise commentary with an informed but balanced tone."""

OPINION_USER_PROMPT = """Based on the research and analysis below, provide editorial commentary.

Research summary:
{research_summary}

Key insights:
{key_insights}

Please include:
1. Editorial perspective
2. Balanced take on controversial points
3. Industry direction
4. Questions readers should watch
"""

EDITOR_SYSTEM_PROMPT = """You are the editor of a technology newsletter.
Compile the provided material into a coherent, readable, professional newsletter
formatted for email delivery."""

EDITOR_USER_PROMPT = """Compile this content into a final newsletter.

Research summary:
{research_summary}

Key insights:
{key_insights}

Opinion and commentary:
{opinion_analysis}

Create:
1. A suggested subject line
2. A short introduction
3. Clear sections
4. Smooth transitions
5. A concise conclusion
6. A short call to action
"""
