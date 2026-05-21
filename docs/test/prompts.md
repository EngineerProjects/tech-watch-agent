# Test Prompts — Tech Watch Agent

Copy/paste each block directly into the **New Session** modal.
Fields map to: `Subject` → `subject`, `Topics` → `topics` (comma-separated), `Research Instructions` → `researchInstructions`.

---

## 01 — Open-source LLMs & reasoning models (weekly)

**Subject:**
What happened this week in open-source LLMs and reasoning models?

**Topics:**
llm, open-source, reasoning, ai-agents, deepseek, qwen, mistral, benchmarks

**Research Instructions:**
Analyze the latest developments from the past 7 days in the open-source LLM ecosystem.

Focus on:
- newly released models
- reasoning-focused architectures (chain-of-thought, tree-of-thought, test-time compute)
- benchmark improvements (MMLU, HumanEval, MATH, GPQA, LiveCodeBench)
- quantization and inference optimizations (GGUF, AWQ, GPTQ, llama.cpp, vLLM)
- trending GitHub repositories (stars, forks, recent commits)
- notable Reddit and Hacker News discussions
- important arXiv papers (last 7 days)
- emerging AI agent frameworks

Compare these model families:
- DeepSeek (V3, R1, R1-Zero variants)
- Qwen (Qwen2.5, QwQ, Qwen-VL)
- Llama (Meta Llama 3.x, community fine-tunes)
- Mistral (Mistral Nemo, Mixtral, Codestral)
- Phi (Microsoft Phi-3, Phi-4)
- Gemma (Google Gemma 2, 3)

Report structure:
1. Executive summary (5 sentences max)
2. Major model releases with parameter counts and benchmark scores
3. Technical breakthroughs — what's genuinely new vs incremental
4. Trending repositories (GitHub links + star counts)
5. Important research papers (arXiv links + 2-sentence summaries)
6. Community reactions (Reddit/HN sentiment, key debates)
7. Weak signals and emerging trends to watch
8. Best resources and links for developers

Prioritize technical depth over general news.
Flag anything that could significantly impact developers or the open-source AI ecosystem.

---

## 02 — Agriculture en Afrique & opportunités foncières

**Subject:**
Évolution agricole en Afrique : où acheter des terres agricoles cette année ?

**Topics:**
agriculture, afrique, terres-agricoles, investissement-foncier, politique-africaine, sécurité-alimentaire, agritech, sahel, afrique-subsaharienne

**Research Instructions:**
Analyse approfondie du marché foncier agricole africain et du contexte politique pour identifier les meilleures opportunités d'investissement.

Axes de recherche :

**Évolution agricole :**
- Nouvelles techniques adoptées en Afrique (irrigation goutte-à-goutte, agriculture de précision, drones agricoles)
- Cultures à forte valeur ajoutée en expansion (cacao, café, quinoa, soja, spiruline)
- Impact du changement climatique sur les zones cultivables
- Programmes FAO, Banque Mondiale et UA pour moderniser l'agriculture africaine
- Startups agritech africaines qui lèvent des fonds en 2026

**Analyse politique par région :**

Afrique de l'Est (priorité haute) :
- Éthiopie : stabilité post-conflit, réformes foncières Abiy Ahmed
- Kenya : cadre juridique pour investisseurs étrangers, terres Rift Valley
- Tanzanie : politique de Magufuli sur la terre, zones économiques spéciales
- Rwanda : modèle de développement, sécurité politique

Afrique de l'Ouest :
- Côte d'Ivoire : stabilité post-Ouattara, cacao et palmier
- Ghana : démocratie solide, cacao et cashew
- Sénégal : réformes Faye/Sonko, nouvelles terres du Sine-Saloum
- Mali/Burkina/Niger : zones à éviter (coups d'état, présence djihadiste)

Afrique du Nord :
- Maroc : agriculture irriguée (Souss-Massa), stabilité monarchique
- Égypte : projets Toshka et Delta, risque politique modéré

Afrique Australe :
- Zambie et Zimbabwe : réforme agraire post-Mugabe, opportunités
- Mozambique : potentiel immense, risques sécuritaires nord

**Critères d'analyse pour chaque pays :**
- Droit de propriété pour les étrangers (achat direct vs bail long terme)
- Stabilité politique (indice de fragilité, risque coup d'état)
- Infrastructures logistiques (routes, ports, eau)
- Prix du foncier ($/hectare) et tendances
- Risques climatiques et hydriques
- Rentabilité estimée (cultures recommandées)

Rapport structuré :
1. Résumé exécutif — top 3 pays recommandés avec justification
2. Carte de risque politique par région
3. Analyse détaillée des 5 meilleurs pays (droit foncier, prix, cultures, risques)
4. Pays à éviter absolument et pourquoi
5. Modèles d'investissement (achat direct, bail emphytéotique, joint-venture local, fonds fonciers)
6. Ressources et contacts (organisations, avocats spécialisés, fonds d'investissement agricole)
7. Signaux faibles — tendances émergentes à surveiller

Comparer les rendements attendus avec d'autres régions (Amérique du Sud, Asie du Sud-Est).

---

## 03 — Intelligence artificielle : toutes les nouveautés du mois

**Subject:**
Toutes les nouveautés importantes en intelligence artificielle ce dernier mois

**Topics:**
intelligence-artificielle, llm, multimodal, agents-ia, diffusion, robotique, openai, anthropic, google, meta-ai, edge-ai, regulation-ia

**Research Instructions:**
Tour d'horizon exhaustif de toutes les avancées significatives en IA sur les 30 derniers jours.

Couverture complète par domaine :

**Modèles de langage (LLMs) :**
- Nouveaux modèles publiés (open-source ET propriétaires)
- Améliorations de performance mesurables (benchmarks)
- Nouvelles architectures (MoE, SSM, hybrides)
- Contextes plus longs, multilingue, code

**IA multimodale :**
- Vision-langage (GPT-4o, Gemini, Claude Vision, Llava)
- Text-to-image (Stable Diffusion, FLUX, Midjourney, DALL-E)
- Text-to-video (Sora, Kling, Runway, Pika Labs)
- Text-to-audio et musique (Suno, Udio, ElevenLabs)
- Text-to-3D et NeRF

**Agents et automatisation :**
- Nouveaux frameworks agents (LangGraph, AutoGen, CrewAI, OpenDevin)
- Computer use et browser automation
- Agents de code (Devin, Cursor, GitHub Copilot updates)
- Pipelines RAG et mémoire long-terme

**IA dans les sciences :**
- Découvertes médicales assistées par IA
- AlphaFold et protéines
- IA climatique et météo
- Mathématiques et démonstrations formelles

**Infrastructure et edge :**
- Inférence locale (Ollama, llama.cpp, MLX sur Apple Silicon)
- Quantization et compression de modèles
- NPU et hardware spécialisé (Apple M4, Qualcomm NPU, Intel Gaudi)
- Coûts d'inférence cloud (comparatif prix/performance)

**IA et développeurs :**
- Nouveaux outils et SDKs (LangChain, LlamaIndex, DSPy)
- Intégrations IDE et plugins VS Code
- APIs notables (Anthropic, OpenAI, Together AI)

**Régulation et éthique :**
- Nouvelles lois et régulations (EU AI Act, USA, Chine)
- Débats sur la sécurité (alignment, red-teaming)
- Impacts emploi et économie

**Startups et financement :**
- Levées de fonds significatives (>10M$)
- Acquisitions notables
- Nouvelles licornes IA

Rapport structuré :
1. Les 10 annonces les plus importantes du mois (résumé avec impact)
2. Tableau comparatif des nouveaux modèles (nom, taille, score clé, licence, date)
3. Ce qui a vraiment changé — percées techniques réelles vs marketing
4. Ce qui va changer dans 3-6 mois (signaux faibles)
5. Ressources pour rester à jour (newsletters, chercheurs à suivre, repos GitHub)

Format : technique et factuel. Éviter la hype. Privilégier les faits mesurables.

---

## 04 — Veille sécurité cyber (hebdomadaire)

**Subject:**
Principales menaces et vulnérabilités cybersécurité de la semaine

**Topics:**
cybersécurité, cve, ransomware, zero-day, apt, cloud-security, supply-chain, malware, threat-intel

**Research Instructions:**
Rapport de threat intelligence hebdomadaire pour équipes SOC et développeurs.

Couvrir :
- CVE critiques publiées cette semaine (CVSS ≥ 8.0) avec logiciels affectés
- Nouvelles campagnes ransomware actives (groupes, secteurs ciblés, TTPs)
- APT et espionnage étatique (Mandiant, CrowdStrike, CISA alerts)
- Vulnérabilités supply chain (npm, PyPI, Docker Hub)
- Incidents cloud majeurs (AWS, Azure, GCP)
- Outils offensifs publiés sur GitHub (red team, pentest)
- Patches urgents Microsoft/Linux/Apple à déployer

Inclure IOCs (IP, domaines, hashes) quand disponibles.
Sources : NVD, CISA KEV, Bleeping Computer, Krebs on Security, TheHacker News, arXiv security.

---

## 05 — Géopolitique tech : la guerre des semi-conducteurs

**Subject:**
Guerre des semi-conducteurs : état des lieux en 2025 entre USA, Chine, Europe et Taïwan

**Topics:**
semi-conducteurs, géopolitique-tech, tsmc, nvidia, huawei, export-control, chips-act, fabrication, supplychain

**Research Instructions:**
Analyse géopolitique et économique de la rivalité technologique autour des semi-conducteurs.

Focus :
- Évolution des restrictions export US (Entity List, BIS rules) et impact sur Huawei/SMIC
- Avancement de TSMC (Arizona, Japon, Allemagne) — retards, subventions, défis
- Samsung et SK Hynix : investissements US et stratégie
- SMIC et l'écosystème chip chinois : où en est la Chine sur les noeuds avancés ?
- ASML : export de machines EUV et DUV vers la Chine
- Chips Act européen : Intel Ireland, TSMC Dresden — réalité vs ambition
- Impact sur le prix des GPU Nvidia (A100, H100, H200, B200) et disponibilité
- Alternatives chinoises (Huawei Ascend, Cambricon, Biren)
- Risques Taiwan Strait sur la supply chain mondiale

Inclure données chiffrées (capacités en wafers/mois, noeuds disponibles, parts de marché).

---

## 06 — Startups deeptech françaises & financement

**Subject:**
Écosystème deeptech et startups IA en France — levées de fonds et innovations récentes

**Topics:**
deeptech, startups-france, french-tech, financement, station-f, quantum, fusion, biotech, ia-france

**Research Instructions:**
État des lieux de l'innovation technologique française sur les 3 derniers mois.

Couvrir :
- Levées de fonds deeptech > 5M€ (IA, quantique, biotech, fusion, spatial)
- Startups IA françaises notables (Mistral AI updates, H company, Poolside, Dust)
- Initiatives BPI France, French Tech, plan France 2030
- Comparatif avec écosystèmes UK, Allemagne, Israël
- Talents et brain drain (chercheurs qui partent vs qui reviennent)
- Régulation IA en France et positionnement européen

Sources : Maddyness, Sifted, Tech.eu, TechCrunch, LinkedIn, BPI France.

---

## 07 — Test charge maximale : recherche académique dense

**Subject:**
State of the art in mechanistic interpretability and sparse autoencoders for transformer LLMs

**Topics:**
mechanistic-interpretability, sparse-autoencoders, superposition, circuits, features, anthropic, eleutherai, transformers, activation-patching

**Research Instructions:**
Deep technical survey of mechanistic interpretability research — last 6 months.

Focus exclusively on:
- Sparse Autoencoder (SAE) methods: training, evaluation, scaling
- Superposition hypothesis: evidence, refutations, open questions
- Circuit analysis: induction heads, indirect object identification, greater-than circuit
- Activation patching and causal mediation analysis
- Feature geometry and polysemanticity
- Scaling laws for interpretability
- Anthropic's dictionary learning work
- EleutherAI and academic lab contributions

Must include:
- arXiv paper links with abstracts
- GitHub repositories with implementation details
- Benchmark comparisons where available
- Open problems and unsolved questions

This is for ML researchers — use precise technical language.
No introductory explanations. Skip basic definitions.
