#!/usr/bin/env python3
"""Builds data/seo-data.js + data/seo-data.json for the Equinet SEO dashboard.

Sources (pulled 2026-08-14, Google Singapore):
- Ahrefs Site Explorer organic keywords for equinetacademy.com (date=2026-08-14,
  compared to 2026-07-14 for previous rank)
- Ahrefs Keywords Explorer (SG) for volume / KD / intent of target keywords
- Ahrefs SERP overview (SG) for competitor rankings
- ClickUp list 901814205053 (SEO Content View / all-courses-iqa) for parent course tasks
"""
import json, os

E = "https://www.equinetacademy.com"
CU = "https://app.clickup.com/t/"
SNAPSHOT = "2026-08-14"
BASELINE = "2026-07-14"

courses = [
 # id, name, url, clickup parent (id, name)
 ("seo","WSQ SEO, AEO, GEO Course", f"{E}/course/seo-training-course-singapore/", "86evuuea2","WSQ SEO, AEO, GEO"),
 ("cseos","Certified SEO Specialist (CSEOS) 2.0", f"{E}/course/certified-seo-specialist-programme/", "86ew9e5t6","Certified SEO Specialist (CSEOS) 2.0"),
 ("dmhub","Digital Marketing Courses (Hub Page)", f"{E}/digital-marketing-courses/", "86evuudeg","WSQ Digital Marketing Foundations (Fundamentals)"),
 ("dmf","WSQ Digital Marketing Foundations (Fundamentals)", f"{E}/course/digital-marketing-foundations-fundamentals-course/", "86evuudeg","WSQ Digital Marketing Foundations (Fundamentals)"),
 ("smm","WSQ Social Media Marketing Strategy & Optimisation", f"{E}/course/social-media-marketing-training-course/", "86evunvj9","WSQ Social Media Marketing Strategy & Optimisation"),
 ("tiktok","WSQ TikTok Marketing", f"{E}/course/tiktok-marketing/", "86evuuh78","WSQ TikTok Marketing"),
 ("meta","WSQ Meta Marketing (Facebook & Instagram)", f"{E}/course/facebook-instagram-marketing-course/", "86evuufyt","WSQ Meta Marketing (Facebook and Instagram)"),
 ("gads","WSQ Google Ads Strategy & Optimisation", f"{E}/course/google-ads-strategy-and-optimisation-course/", "86evuugjk","WSQ Google Ads Strategy and Optimisation"),
 ("ga4","WSQ Digital Marketing Analytics & Optimisation (GA4)", f"{E}/course/digital-web-analytics-google-analytics-training-course/", "86ewz31jq","WSQ Digital Marketing Analytics & Optimisation (Google Analytics 4) Course"),
 ("content","WSQ Digital Content Creation & Content Marketing Strategy", f"{E}/course/content-marketing-course/", "86evuue40","WSQ Digital Content Creation & Content Marketing Strategy Course"),
 ("dcc","WSQ Digital Content Creation for Content Creators", f"{E}/course/digital-content-creation-course/", "86evv6udp","WSQ Digital Content Creation For Content Creators"),
 ("copy","WSQ Digital Copywriting & Content Writing", f"{E}/course/copywriting-course/", "86evv5bwr","WSQ Digital Copywriting and Content Writing Course"),
 ("ecom","Ecommerce Strategy Course", f"{E}/course/ecommerce-strategy-course/", "86ey3acx0","Ecommerce Strategy"),
 ("shopee","WSQ Ecommerce Marketplaces (Shopee & Lazada)", f"{E}/course/ecommerce-marketplaces-shopee-lazada-course/", "86evv9b7w","WSQ Ecommerce Marketplaces (Shopee & Lazada)"),
 ("uxui","WSQ UX/UI Design Essentials", f"{E}/course/wsq-user-experience-user-interface-ux-ui-design-essentials/", "86evw9x34","WSQ User Experience & User Interface (UX UI) Design Essentials"),
 ("auxui","WSQ Advanced UX/UI Design", f"{E}/course/advanced-ux-ui-design-course/", "86evw9n2c","WSQ Advanced UX UI Design"),
 ("wp","WSQ WordPress Website Creation", f"{E}/course/wordpress-website-landing-page-creation-course-singapore/", "86ey7p18b","WordPress Website & Landing Page Creation Course"),
 ("clpds","Certified Landing Page & Web Design Specialist (CLPDS)", f"{E}/course/certified-landing-page-design-specialist-clpds/", "86ew9e60a","Certified Landing Page & Web Design Specialist (CLPWDS)"),
 ("canva","WSQ Canva Design", f"{E}/course/canva-design-course/", "86evwarrf","WSQ Canva Design"),
 ("dx","WSQ AI-Driven Digital Transformation", f"{E}/course/digital-transformation-course/", "86evw9q3d","WSQ AI-Driven Digital Transformation"),
 ("aidm","WSQ AI in Digital Marketing", f"{E}/course/ai-in-digital-marketing/", "86evuudfn","WSQ AI in Digital Marketing"),
 ("genai","Generative AI Applications Course", f"{E}/course/generative-ai-chatgpt-gemini-and-popular-ai-tools-course/", "86ew9p1wf","Generative AI Applications (ChatGPT, Claude, and Mainstream AI Tools) for Productivity & Business"),
 ("aiess","AI Essentials Course", f"{E}/course/ai-and-machine-learning-course/", "86extf6xw","AI Essentials"),
 ("agentic","Agentic AI Course", f"{E}/course/agentic-ai-course/", "86ew9qa2a","Agentic AI"),
 ("prompt","Prompt Engineering Course", f"{E}/course/prompt-engineering-course/", "86ew9p1v0","Prompt Engineering"),
 ("pbi","WSQ Power BI Course", f"{E}/course/power-bi-course/", "86evw9w8x","WSQ Power BI"),
 ("tableau","Tableau Data Visualisation & Dashboarding", f"{E}/course/tableau-data-visualisation-and-dashboarding-course/", "86ew9xv65","Tableau Data Visualisation & Dashboarding"),
 ("da","Data Analytics & Data Literacy Essentials", f"{E}/course/data-analytics-and-data-literacy-essentials-course/", "86ew9xr2k","Data Analytics and Data Literacy Essentials"),
 ("cyber","Cybersecurity Awareness & Essentials", f"{E}/course/cybersecurity-awareness-essentials-for-workplace-employees-business-owners-course/", "86ew9y01r","Cybersecurity Awareness & Essentials For Workplace Employees & Business Owners"),
 ("video","Video Creation & Video Editing (Digital Storytelling)", f"{E}/course/video-creation-video-editing-digital-storytelling-course/", "86evw9xfz","Video Creation & Video Editing (Digital Storytelling)"),
 ("photo","Mirrorless & DSLR Photography Essentials", f"{E}/course/mirrorless-dslr-photography-essentials-course/", "86ew9yyeh","Mirrorless & DSLR Photography Essentials Course"),
 ("pubspeak","Public Speaking Course", f"{E}/course/public-speaking-course/", "86evw9whf","Public Speaking"),
 ("entre","Entrepreneurship Course", f"{E}/course/entrepreneurship-course/", "86evw9q9e","Entrepreneurship"),
 ("figma","WSQ What The Figma (WTF)", f"{E}/course/what-the-figma-wtf/", "86evw9xj7","WSQ What The Figma (WTF)"),
 ("email","WSQ Email Marketing & Marketing Automation", f"{E}/course/email-marketing-and-marketing-automation-course/", "86evuueg8","WSQ Email Marketing & Marketing Automation"),
]

def C(name, url, pos, dr=None):
    return {"name": name, "url": url, "pos": pos, "dr": dr}

ask = "asktraining.com.sg"; smu = "academy.smu.edu.sg"; ntuc = "ntuclearninghub.com"
tert = "tertiarycourses.com.sg"; oom = "oom.com.sg"; msf = "courses.myskillsfuture.gov.sg"

# keyword rows: kw, course, primary, vol, kd, cpc, intent, rank, prev, rankUrl(path), competitor, gap, coveredBy, cannibal, opportunity
K = []
def kw(kwd, course, primary, vol, kd, intent, rank, prev, rankPath, comp, gap, coveredBy, cannibal, opp, cpc=None):
    K.append({
        "id": f"kw-{len(K)+1:02d}", "kw": kwd, "courseId": course, "primary": primary,
        "vol": vol, "kd": kd, "cpc": cpc, "intent": intent,
        "rank": rank, "prevRank": prev,
        "rankUrl": (E + rankPath) if rankPath else None,
        "competitor": comp, "gap": gap, "coveredBy": coveredBy,
        "cannibal": cannibal, "opportunity": opp,
        "history": ([{"date": BASELINE, "rank": prev}] if prev else []) + ([{"date": SNAPSHOT, "rank": rank}] if rank else []),
    })

# ---- SEO ----
kw("seo course singapore","seo",True,250,0,"Transactional / Commercial / Local",5,5,"/course/seo-training-course-singapore/",
   C(ask,"https://asktraining.com.sg/digital-marketing-courses/wsq-search-engine-optimisation-course/",2,36),
   "page1-to-top3",None,
   "Low-medium: legacy /course/seo-training-course/ still live with near-identical targeting ('WSQ Search Engine Optimisation (SEO) Strategy Course') — verify canonical/redirect. /course/advanced-seo-course/ and CSEOS 2.0 target adjacent intents.",
   "KD 0 with rank 5 — Ask Training (DR 36) holds #2 with a weaker profile; on-page refresh + internal links can realistically win top 3.")
kw("seo training singapore","seo",False,150,0,"Transactional / Commercial / Local",2,3,"/course/seo-training-course-singapore/",
   C(ask,"https://asktraining.com.sg/digital-marketing-courses/search-engine-optimisation/",3,36),
   "top3-to-1",None,None,"Already #2 and improving (was #3). #1 within reach with fresh content + review schema.")
kw("seo course","seo",False,150,8,"Commercial / Informational",6,8,"/course/seo-training-course-singapore/",None,"page1-to-top3",None,None,"Improved 8→6; consolidate gains with content depth (AEO/GEO sections match new title).")
kw("seo training course","seo",False,150,18,"Transactional / Commercial",7,6,"/course/seo-training-course-singapore/",None,"page1-to-top3",None,None,"Slipped 6→7 — watch; strengthen internal anchors from SEO blog cluster.")
kw("seo courses singapore","seo",False,40,0,"Transactional / Commercial / Local",1,3,"/course/seo-training-course-singapore/",None,"defend",None,None,"Reached #1 (was #3). Defend with rank monitoring.")
kw("seo certification","cseos",True,70,39,"Commercial / Informational",1,1,"/course/certified-seo-specialist-programme/",None,"defend",None,
   "Low: WSQ SEO course page targets course intent; keep certification intent on CSEOS.",
   "Ranking #1. Maintain freshness; add FAQ schema to hold the position against Coursera/HubSpot.")

# ---- Digital marketing hub ----
kw("digital marketing course","dmhub",True,700,10,"Commercial / Informational",10,1,"/digital-marketing-courses/",
   C(smu,"https://academy.smu.edu.sg/courses/professional-certificate-digital-marketing",2,79),
   "recover-decline",None,
   "HIGH: blog 'How to Do Digital Marketing: A Beginner's Guide' has also ranked #1 for this keyword; multiple pages (hub, foundations course, CDMS programme, blog guide) target overlapping intent.",
   "CRITICAL DECLINE: #1 → #10 in one month on the highest-value keyword (700/mo). Diagnose: cannibalisation with blog guide + content freshness. Recovery = biggest single traffic win available.")
kw("digital marketing course singapore","dmhub",True,600,7,"Commercial / Informational / Local",13,11,"/digital-marketing-courses/",
   C(smu,"https://academy.smu.edu.sg/courses/professional-certificate-digital-marketing",2,79),
   "page2-to-page1",None,"HIGH: same cluster as 'digital marketing course'.",
   "Page 2 (#13) on a 600/mo KD 7 keyword. SMU (#2) and Ask Training (#4) rank with standard course pages — hub page consolidation + backlinks can return this to page 1.")
kw("digital marketing courses singapore","dmhub",False,300,2,"Commercial / Informational / Local",11,1,"/digital-marketing-courses/",None,"recover-decline",None,"HIGH: same cluster.","Dropped #1 → #11. Same recovery cluster as 'digital marketing course'.")
kw("wsq diploma in digital marketing","dmhub",False,150,6,"Commercial / Branded",3,3,"/digital-marketing-courses/",None,"top3-to-1",None,None,"Stable #3; low effort to defend.")
kw("digital marketing course skillsfuture","dmhub",False,150,6,"Commercial / Branded",8,5,"/digital-marketing-courses/",None,"recover-decline",None,None,"Slipped 5→8; add a dedicated SkillsFuture funding section on the hub.")
kw("best digital marketing course singapore","dmhub",False,70,6,"Commercial / Local",2,2,"/digital-marketing-courses/",None,"defend",None,None,"Stable #2. Defend.")
kw("marketing courses singapore","dmhub",False,150,17,"Transactional / Commercial / Local",8,8,"/digital-marketing-courses/",None,"page1-to-top3",None,None,"Stable #8; broader head term — supporting content + links.")

# ---- DM Foundations ----
kw("fundamentals of digital marketing","dmf",True,60,3,"Informational / Branded",9,4,"/course/digital-marketing-foundations-fundamentals-course/",None,"recover-decline",None,None,"Dropped 4→9. Refresh course page content; re-add fundamentals FAQ.")
kw("digital marketing fundamentals","dmf",False,20,23,"Commercial / Informational",6,3,"/course/digital-marketing-foundations-fundamentals-course/",None,"recover-decline",None,None,"Dropped 3→6 — same refresh.")
kw("wsq digital marketing course","dmf",False,100,None,"Commercial / Branded",None,None,None,None,"competitor-gap",
   f"{E}/course/digital-marketing-strategy-course/ ranks #3 for 'wsq digital marketing'","Medium: strategy course page captures the WSQ modifier instead of foundations/hub.",
   "Not ranking for the exact phrase (100/mo). Assign to hub or foundations page and align title tags.")

# ---- Social media ----
kw("social media course","smm",True,150,10,"Commercial / Informational",6,6,"/course/social-media-marketing-training-course/",
   C(smu,"https://academy.smu.edu.sg/courses/digital-marketing-social-media-marketing",2,79),
   "page1-to-top3",None,
   "Medium: blog 'Winning 6-Step Social Media Marketing Strategy' also surfaces for this keyword — align internal links to the course page.",
   "Stable #6, KD 10. SMU #2 / Ask Training #4; optimised title + review schema + blog internal links can reach top 3.")
kw("social media courses singapore","smm",False,100,1,"Commercial / Local",7,7,"/course/social-media-marketing-training-course/",None,"page1-to-top3",None,None,"Stable #7; same cluster.")
kw("social media marketing course singapore","smm",False,30,0,"Transactional / Commercial / Local",3,7,"/course/social-media-marketing-training-course/",None,"top3-to-1",None,None,"Improved 7→3 — momentum; push to #1.")
kw("social media marketing course","smm",False,150,25,"Commercial / Informational",None,None,None,
   C(smu,"https://academy.smu.edu.sg/courses/digital-marketing-social-media-marketing",2,79),
   "competitor-gap",None,None,"Competitors rank, Equinet doesn't (150/mo). Fold exact phrase into course page H1/meta.")

# ---- TikTok ----
kw("tiktok course singapore","tiktok",True,100,0,"Transactional / Commercial / Local",6,6,"/course/tiktok-marketing/",
   C(smu,"https://academy.smu.edu.sg/courses/tiktok-marketing-and-ads-business",1,79),
   "page1-to-top3",None,None,"Stable #6, KD 0. SMU #1, BELLS #2, Ask Training #4 — striking distance (existing ClickUp task covers this).")
kw("tiktok course","tiktok",False,80,0,"Transactional / Commercial / Branded",9,8,"/course/tiktok-marketing/",None,"page1-to-top3",None,None,"Slipped 8→9; same optimisation cluster.")
kw("tiktok marketing course","tiktok",False,150,None,"Commercial",None,None,None,
   C(ask,"https://asktraining.com.sg/digital-marketing-courses/tiktok-marketing/",4,36),
   "competitor-gap",None,None,"150/mo variant not captured — add exact phrase to title/H1.")

# ---- Meta ----
kw("facebook marketing course","meta",True,90,0,"Commercial / Informational",4,4,"/course/facebook-instagram-marketing-course/",None,"page1-to-top3",None,
   "Low: blog 'Beginner's Guide to Facebook Marketing' targets informational intent — good internal-link source.",
   "Stable #4, KD 0 — top 3 achievable with refreshed title/meta + FAQ.")
kw("facebook ads course","meta",False,70,26,"Commercial / Branded",None,None,None,None,"competitor-gap",None,None,
   "Not ranking (70/mo). Add 'Facebook Ads' module section on Meta Marketing page.")

# ---- Google Ads ----
kw("google ads course","gads",True,200,12,"Commercial / Informational / Branded",8,8,"/course/google-ads-strategy-and-optimisation-course/",
   C(ask,"https://asktraining.com.sg/digital-marketing-courses/wsq-google-ads-course/",5,36),
   "page1-to-top3",None,None,
   "Stable #8. Skillshop/Google own top spots (navigational) but Ask Training #5 proves a local WSQ page can sit top 5.")
kw("google ads course singapore","gads",False,150,None,"Commercial / Local",None,None,None,
   C(ask,"https://asktraining.com.sg/digital-marketing-courses/wsq-google-ads-course/",5,36),
   "competitor-gap",None,None,"150/mo local variant not captured — add 'Singapore' to title tag and on-page copy.")

# ---- GA4 ----
kw("google analytics course singapore","ga4",True,70,0,"Transactional / Commercial / Local",4,3,"/course/digital-web-analytics-google-analytics-training-course/",
   C("sutd.edu.sg","https://www.sutd.edu.sg/academy-course/google-analytics-mastery-the-data-driven-approach-to-digital-marketing/",1,74),
   "page1-to-top3",None,None,"#4 (was #3). SUTD #1, Ask Training #2, OOm #3 — refresh + GA4 keyword alignment to reclaim top 3.")
kw("ga4 course","ga4",False,100,None,"Commercial",None,None,None,None,"competitor-gap",None,
   "Low: blog 'GA4 Certification' covers certification intent — internal link, don't duplicate.",
   "100/mo not captured — add explicit 'GA4 course' phrasing on the analytics course page.")
kw("ga4 certification","ga4",False,20,56,"Commercial / Branded",6,4,"/blog/ga4-certification-what-it-is-and-why-it-matters/",None,"page1-to-top3",
   "Blog article (not course page)",None,"Blog ranks #6 (was #4). Optimise article + strengthen internal link to GA4 course.")

# ---- Content marketing ----
kw("content marketing singapore","content",True,300,2,"Commercial / Informational",5,5,"/course/content-marketing-course/",
   C(smu,"https://academy.smu.edu.sg/courses/content-marketing-and-search-engine-optimisation-seo",8,79),
   "page1-to-top3",None,
   "Low-medium: strong blog cluster (what-is-content-marketing, content pillars) targets informational variants — keep intents separated.",
   "#5 on 300/mo KD 2. SERP is mixed-intent (jobs, agencies) — the only course result above Equinet is none; top-3 realistic with stronger relevance signals.")
kw("content marketing course","content",False,150,35,"Commercial / Informational",None,None,None,
   C("academy.hubspot.com","https://academy.hubspot.com/courses/content-marketing",1,93),
   "competitor-gap",None,None,"Global players (HubSpot, Coursera) + SUSS/SMU own this SERP. Long-term: build authority; short-term: target 'content marketing course singapore' (70/mo).")
kw("content creation course","dcc",True,250,0,"Transactional / Commercial / Local",2,4,"/course/digital-content-creation-course/",None,"top3-to-1",None,None,"Improved 4→2, KD 0 — #1 within reach; add review schema + internal links.")
kw("digital content creation","dcc",False,100,0,"Commercial / Informational",8,6,"/course/digital-content-creation-course/",None,"page1-to-top3",None,None,"Slipped 6→8; refresh copy.")

# ---- Copywriting ----
kw("copywriting courses singapore","copy",True,40,0,"Transactional / Commercial / Local",3,4,"/course/copywriting-course/",None,"top3-to-1",None,None,"Improved 4→3; push to #1 (KD 0).")
kw("copywriting course","copy",False,60,15,"Transactional / Commercial / Local",9,7,"/course/copywriting-course/",None,"recover-decline",None,
   "Low: blog 'Copywriting vs Content Writing' is complementary — internal link source.",
   "Slipped 7→9; refresh content + internal links from copywriting blog.")
kw("copywriting courses","copy",False,70,13,"Commercial / Informational",8,None,"/course/copywriting-course/",None,"new-ranking",None,None,"New ranking at #8 — consolidate.")
kw("copywriting course singapore","copy",False,10,0,"Transactional / Commercial / Local",2,7,"/course/copywriting-course/",None,"top3-to-1",None,None,"Improved 7→2.")

# ---- Ecommerce ----
kw("ecommerce course singapore","ecom",True,150,0,"Commercial / Informational / Local",3,4,"/course/ecommerce-strategy-course/",
   C(tert,"https://www.tertiarycourses.com.sg/ecommerce-training-courses.html",1,40),
   "top3-to-1",None,
   "Low-medium: /ecommerce-courses/ hub also ranks for 'ecommerce courses' — keep hub for plural/category, course page for exact.",
   "Improved 4→3, KD 0. Tertiary Courses #1 (DR 40) is beatable — content depth + reviews to take #1.")
kw("ecommerce course","ecom",False,60,19,"Transactional / Commercial",5,5,"/course/ecommerce-strategy-course/",None,"page1-to-top3",None,None,"Stable #5.")
kw("shopee lazada","shopee",True,40,66,"Commercial / Branded",7,None,"/course/ecommerce-marketplaces-shopee-lazada-course/",None,"new-ranking",None,None,"New ranking #7 on a branded head term — expand marketplace-seller content.")

# ---- UX/UI ----
kw("ux ui","uxui",True,100,43,"Commercial / Informational",5,4,"/course/wsq-user-experience-user-interface-ux-ui-design-essentials/",
   C(smu,"https://academy.smu.edu.sg/courses/ui-ux-course",2,79),
   "page1-to-top3",None,
   "HIGH: Essentials, Advanced UX/UI, CUXD and the /user-experience-ux-design-creative-courses/ hub all rank for overlapping UX keywords — consolidate targeting before further optimisation.",
   "#5 (was #4) on the head term. Fix cluster cannibalisation first, then push.")
kw("ux courses singapore","uxui",False,100,0,"Transactional / Commercial / Local",9,9,"/course/wsq-user-experience-user-interface-ux-ui-design-essentials/",None,"page1-to-top3",None,None,"Stable #9, KD 0 — good striking-distance target.")
kw("ui ux course singapore","uxui",False,90,0,"Commercial / Local",8,8,"/course/wsq-user-experience-user-interface-ux-ui-design-essentials/",None,"page1-to-top3",None,None,"Stable #8, KD 0.")
kw("ux design course singapore","uxui",False,60,0,"Transactional / Commercial / Local",7,8,"/course/wsq-user-experience-user-interface-ux-ui-design-essentials/",None,"page1-to-top3",None,None,"Improved 8→7.")
kw("ui ux design course","auxui",True,80,20,"Commercial / Informational",7,None,"/course/advanced-ux-ui-design-course/",
   C(smu,"https://academy.smu.edu.sg/courses/ui-ux-course",2,79),
   "new-ranking",None,"HIGH: Advanced page ranking for a generic course keyword the Essentials page should own.",
   "New at #7 — but on the wrong page for the intent (beginners land on Advanced). Resolve with the UX cluster consolidation.")
kw("ux ui course","auxui",False,30,33,"Transactional / Commercial",3,4,"/course/advanced-ux-ui-design-course/",None,"top3-to-1",None,"Same UX cluster overlap.","Improved 4→3.")

# ---- WordPress / web design ----
kw("wordpress course","wp",True,90,15,"Commercial / Branded",2,1,"/course/wordpress-website-landing-page-creation-course-singapore/",
   C("learn.wordpress.org","https://learn.wordpress.org/courses/",1,97),
   "defend",None,None,"#2 behind learn.wordpress.org (navigational, DR 97) — #2 is effectively #1 for commercial intent. Defend.")
kw("wordpress training singapore","wp",False,100,0,"Transactional / Commercial / Local",5,6,"/course/wordpress-website-landing-page-creation-course-singapore/",None,"page1-to-top3",None,None,"Improved 6→5, KD 0 — top 3 realistic.")
kw("wordpress course singapore","wp",False,50,0,"Transactional / Commercial / Local",3,5,"/course/wordpress-website-landing-page-creation-course-singapore/",None,"top3-to-1",None,None,"Improved 5→3.")
kw("web design course singapore","clpds",True,150,0,"Commercial / Local",10,12,"/course/certified-landing-page-design-specialist-clpds/",
   C(tert,"https://www.tertiarycourses.com.sg/web-design-courses.html",1,40),
   "page1-to-top3",None,
   "Medium: CLPDS, WSQ Landing Page Design and WordPress course all touch web-design intent — pick CLPDS as the target page.",
   "Improved 12→10 on 150/mo KD 0. Competitors are DR 35-40 — a dedicated 'web design course' content block + internal links can reach top 5.")
kw("website design course singapore","clpds",False,100,0,"Transactional / Commercial / Local",10,8,"/course/certified-landing-page-design-specialist-clpds/",None,"recover-decline",None,None,"Slipped 8→10 — same cluster.")

# ---- Canva ----
kw("canva course","canva",True,60,20,"Informational / Branded",6,6,"/course/canva-design-course/",None,"page1-to-top3",None,None,"Stable #6. Supporting Canva guide (already a ClickUp task) + internal link should lift it.")
kw("canva course singapore","canva",False,100,None,"Commercial / Local",None,None,None,None,"competitor-gap",None,None,"100/mo local variant not captured — add 'Singapore' phrasing to title/H1.")

# ---- Digital transformation ----
kw("digital transformation courses","dx",True,100,0,"Commercial / Informational",3,7,"/course/digital-transformation-course/",
   C(ntuc,"https://www.ntuclearninghub.com/digital-transformation",1,62),
   "top3-to-1",None,None,"Improved 7→3 — strong momentum; NTUC #1.")
kw("digital transformation course","dx",False,60,2,"Commercial / Informational",6,9,"/course/digital-transformation-course/",None,"page1-to-top3",None,None,"Improved 9→6.")
kw("digital transformation course singapore","dx",False,150,0,"Commercial / Local",None,None,None,
   C(ntuc,"https://www.ntuclearninghub.com/digital-transformation",1,62),
   "competitor-gap",None,None,"Largest DX variant (150/mo, KD 0) not captured — add exact local phrasing.")

# ---- AI cluster ----
kw("ai marketing course","aidm",True,50,None,"Commercial",None,None,None,None,"no-visibility",None,None,
   "Page only ranks for branded terms. Optimise for 'AI marketing course' / 'AI in digital marketing course'.")
kw("generative ai course singapore","genai",True,400,7,"Commercial / Local",None,None,None,
   C(smu,"https://academy.smu.edu.sg/generative-ai-courses",1,79),
   "competitor-gap",None,None,
   "400/mo KD 7 and no Equinet visibility. SMU #1, Vertical Institute #2 (DR 40), Heicoders #4 (DR 43) — mid-DR sites rank, so Equinet (DR 41) can compete with an optimised page.")
kw("chatgpt course singapore","genai",False,150,0,"Commercial / Branded / Local",None,None,None,None,"competitor-gap",None,None,
   "150/mo KD 0 — add ChatGPT-focused section/FAQ on the GenAI course page.")
kw("ai course singapore","aiess",True,1700,26,"Commercial / Informational / Local",None,None,None,
   C(smu,"https://academy.smu.edu.sg/ai-courses-singapore",3,79),
   "competitor-gap",None,None,
   "Highest-volume opportunity (1,700/mo). SERP is directory/institution-heavy; realistic path = optimise AI Essentials page + AI hub/supporting content + backlinks. Long-term play.")
kw("agentic ai course","agentic",True,200,6,"Commercial / Informational",None,None,None,
   C(tert,"https://www.tertiarycourses.com.sg/wsq-agentic-ai-courses.html",4,40),
   "competitor-gap",None,None,
   "200/mo KD 6, growing fast. Tertiary Courses #4 shows local providers can rank. Existing ClickUp cluster task covers this.")
kw("prompt engineering course singapore","prompt",True,300,None,"Commercial / Local",None,None,None,None,"competitor-gap",None,None,
   "300/mo, no visibility. Optimise course page (title/H1/meta with 'Singapore', SkillsFuture section).")
kw("prompt engineering course","prompt",False,350,18,"Commercial / Informational",None,None,None,None,"competitor-gap",None,None,"350/mo global-intent variant — same page.")

# ---- Data / BI ----
kw("power bi course singapore","pbi",True,350,0,"Transactional / Commercial / Local",None,None,None,
   C(ntuc,"https://www.ntuclearninghub.com/-/course/analyzing-and-visualizing-data-with-power-bi-sf",3,62),
   "competitor-gap",None,None,
   "350/mo KD 0 with zero visibility — biggest quick-win gap. JCI (DR 7!) ranks #6; an optimised WSQ Power BI page should enter top 10 fast.")
kw("power bi course","pbi",False,500,47,"Commercial / Branded",None,None,None,None,"competitor-gap",None,None,"500/mo KD 47 — secondary target once SG variant ranks.")
kw("tableau course singapore","tableau",True,150,0,"Informational / Commercial",None,None,None,
   C(ask,"https://asktraining.com.sg/microsoft-excel-courses/data-visualisation-and-storytelling-with-tableau/",2,36),
   "competitor-gap",None,None,"150/mo KD 0, no visibility. JCI (DR 7) ranks #8 — highly winnable.")
kw("data analytics course singapore","da",True,200,52,"Commercial / Local",None,None,None,
   C("scale.nus.edu.sg","https://scale.nus.edu.sg/programmes/lifelonglearning/data-analytics",2,86),
   "competitor-gap",None,None,"200/mo KD 52 — institution-heavy SERP. Long-term: supporting content + internal links; short-term: target long-tails ('data analytics course for beginners singapore').")
kw("business analytics course singapore","da",False,150,2,"Transactional / Commercial / Local",None,None,None,None,"competitor-gap",None,None,"150/mo KD 2 — map to Business Analytics / Data Analytics pages.")

# ---- Cybersecurity ----
kw("cybersecurity course singapore","cyber",True,500,2,"Transactional / Commercial / Local",None,None,None,
   C("iss.nus.edu.sg","https://www.iss.nus.edu.sg/executive-education/discipline/detail/cybersecurity",2,86),
   "competitor-gap",None,
   "Low: 4 cybersecurity blog posts exist (internship, act, degree) — internal-link assets, different intent.",
   "500/mo KD 2 with zero course-page visibility. CFCI (DR 27) ranks #8 — a focused optimisation + internal links from the 4 cyber blog posts can break top 10.")
kw("cybersecurity awareness training","cyber",False,150,None,"Commercial",None,None,None,None,"competitor-gap",None,None,"150/mo exact-match to the course's positioning — add to title/meta.")

# ---- Creative ----
kw("video editing course singapore","video",True,250,0,"Transactional / Commercial / Local",None,None,None,
   C(ask,"https://asktraining.com.sg/media-production-courses/video-production/",3,36),
   "competitor-gap",None,None,"250/mo KD 0, no visibility. Hustle (DR 13) and Coursemology (DR 36) rank — very winnable for DR 41.")
kw("videography course singapore","video",False,60,0,"Transactional / Commercial / Local",None,None,None,None,"competitor-gap",None,None,"60/mo KD 0 — same cluster (videography essentials course).")
kw("photography course singapore","photo",True,200,4,"Transactional / Commercial / Local",None,None,None,None,"competitor-gap",None,None,"200/mo KD 4, no visibility despite 6+ photography courses. Optimise essentials page or create a photography category hub.")

# ---- Business skills ----
kw("public speaking course singapore","pubspeak",True,300,11,"Transactional / Commercial / Local",None,None,None,None,"competitor-gap",None,None,"300/mo KD 11 — no visibility. On-page optimisation first.")
kw("entrepreneurship course singapore","entre",True,150,0,"Transactional / Commercial / Local",None,None,None,None,"competitor-gap",None,
   "Low: entrepreneurship blog posts exist — internal-link assets.",
   "150/mo KD 0 — optimise course page + internal links from 3 entrepreneurship blog posts.")
kw("figma course singapore","figma",True,60,None,"Commercial / Local",None,None,None,None,"competitor-gap",None,None,"60/mo — align WTF course title with 'Figma course Singapore'.")
kw("email marketing course singapore","email",True,90,None,"Commercial / Local",None,None,None,None,"competitor-gap",None,None,"90/mo — optimise course page title/H1.")
kw("sales courses singapore","entre",False,150,0,"Transactional / Commercial / Local",5,7,"/sales-courses-singapore/",None,"page1-to-top3",
   "Sales category hub page",None,"Hub improved 7→5 (KD 0) — internal links + hub content to reach top 3.")

# ---------- Supporting content ----------
blog = lambda p: f"{E}/blog/{p}/"
CONTENT = [
 dict(courseId="dmhub", kw="digital marketing course", vol=700, kd=10, intent="Commercial",
      existing=[{"title":"How to Do Digital Marketing: A Beginner's Guide","url":blog("how-to-do-digital-marketing-a-beginners-guide")},
                {"title":"What is Digital Marketing? Digital Marketing Strategy","url":blog("what-is-digital-marketing-digital-marketing-strategy")}],
      risk="High", rec="Optimise Existing Article", newTopic=None,
      targetUrl=f"{E}/digital-marketing-courses/",
      link="Re-point 'digital marketing course'-anchored internal links from both articles to the hub page; keep articles focused on informational how-to intent.",
      reason="Hub dropped #1→#10 while the beginner's-guide article competes for the same commercial keyword. De-optimise the article for course intent instead of creating anything new.",
      status="Live"),
 dict(courseId="seo", kw="seo vs sem / seo fundamentals", vol=150, kd=6, intent="Informational",
      existing=[{"title":"SEO vs SEM: Which Should You Focus On First?","url":blog("seo-vs-sem")},
                {"title":"SEO Packages, Pricing & Costs Guide","url":blog("seo-packages-pricing-and-costs-a-comprehensive-guide")}],
      risk="Low", rec="Optimise Existing Article", newTopic=None,
      targetUrl=f"{E}/course/seo-training-course-singapore/",
      link="Add contextual CTA + exact-anchor link 'SEO course Singapore' from both articles to the course page.",
      reason="SEO vs SEM already ranks for 12 keywords (#6 'seo sem marketing'); a 2026 refresh with AEO/GEO section supports the renamed course. A ClickUp distribution task for this article already exists.",
      status="Live"),
 dict(courseId="smm", kw="social media marketing strategy", vol=200, kd=10, intent="Informational",
      existing=[{"title":"Winning 6-Step Social Media Marketing Strategy","url":blog("winning-6-step-social-media-marketing-strategy")},
                {"title":"When Is the Best Time to Post on Social Media","url":blog("when-is-the-best-time-to-post-on-social-media-platform-by-platform-breakdown")},
                {"title":"15 Types of Social Media Content That Work","url":blog("15-types-of-social-media-content-that-work-examples")}],
      risk="Medium", rec="Optimise Existing Article", newTopic=None,
      targetUrl=f"{E}/course/social-media-marketing-training-course/",
      link="Strategy article surfaces for 'social media course' — keep it informational and link its course mentions to the course page.",
      reason="Strong existing cluster; no new article needed. Optimising and interlinking beats new content.",
      status="Live"),
 dict(courseId="tiktok", kw="tiktok marketing strategies", vol=150, kd=0, intent="Informational",
      existing=[{"title":"8 TikTok Marketing Strategies for Businesses in Singapore","url":blog("8-tiktok-marketing-strategies-for-businesses-in-singapore")},
                {"title":"Top 10 TikTok Marketing Agencies","url":blog("top-10-tiktok-marketing-agencies-that-help-grow-your-brand-online")}],
      risk="Low", rec="Optimise Existing Article", newTopic=None,
      targetUrl=f"{E}/course/tiktok-marketing/",
      link="Add course CTA + exact-anchor 'TikTok course Singapore' link from both posts.",
      reason="Existing strategies post ranks #10 for 'tik tok marketing' — expanding it supports the course page. Covered by existing ClickUp task 'Optimise TikTok Marketing Skills Content'.",
      status="Live"),
 dict(courseId="ga4", kw="ga4 certification", vol=20, kd=56, intent="Commercial",
      existing=[{"title":"GA4 Certification: What It Is and Why It Matters","url":blog("ga4-certification-what-it-is-and-why-it-matters")},
                {"title":"11 GA4 Metrics All Websites Should Track","url":blog("11-google-analytics-4-metrics-all-websites-should-track")}],
      risk="Low", rec="Optimise Existing Article", newTopic=None,
      targetUrl=f"{E}/course/digital-web-analytics-google-analytics-training-course/",
      link="Both GA4 articles → analytics course page with 'Google Analytics course Singapore' anchors.",
      reason="Certification article slipped #4→#6; refresh and interlink rather than creating new GA4 content.",
      status="Live"),
 dict(courseId="cyber", kw="cybersecurity careers / awareness", vol=500, kd=2, intent="Informational",
      existing=[{"title":"Cybersecurity Internship Singapore","url":blog("cybersecurity-internship-singapore-what-to-expect-and-how-to-succeed")},
                {"title":"What is the Cybersecurity Act in Singapore","url":blog("what-is-the-cybersecurity-act-in-singapore-and-how-it-protects-your-organisation")},
                {"title":"Do You Really Need a Cybersecurity Degree in Singapore","url":blog("do-you-really-need-a-cybersecurity-degree-in-singapore-to-succeed")}],
      risk="Low", rec="Optimise Existing Article", newTopic=None,
      targetUrl=f"{E}/course/cybersecurity-awareness-essentials-for-workplace-employees-business-owners-course/",
      link="All 3 cyber posts currently drive traffic with no course CTA — add in-content links + end-of-article course banner to the Cybersecurity Awareness course.",
      reason="Topical authority already exists in the blog; the course page just isn't connected to it. Internal linking is the highest-ROI fix before any new content.",
      status="Live"),
 dict(courseId="ecom", kw="ecommerce guides", vol=500, kd=10, intent="Informational",
      existing=[{"title":"How to Choose the Best Products to Sell Online in Singapore","url":blog("how-to-choose-the-best-products-to-sell-online-in-singapore")},
                {"title":"How to Launch Your Dropshipping Business in Singapore","url":blog("how-to-launch-your-dropshipping-business-in-singapore-a-step-by-step-guide-for-new-entrepreneurs")},
                {"title":"What is E-commerce and How to Start Your Own Online Business","url":blog("what-is-e-commerce-and-how-to-start-your-own-online-business")},
                {"title":"PSG Ecommerce Grant by Enterprise Singapore","url":blog("psg-ecommerce-grant-by-enterprise-singapore-all-you-need-to-know")}],
      risk="Low", rec="Optimise Existing Article", newTopic=None,
      targetUrl=f"{E}/course/ecommerce-strategy-course/",
      link="Add 'ecommerce course Singapore' anchors from all 4 posts to the Ecommerce Strategy course (currently #3 — links help take #1).",
      reason="Large existing ecommerce cluster already ranks; interlinking beats new content.",
      status="Live"),
 dict(courseId="genai", kw="ai tools for marketing", vol=80, kd=5, intent="Informational",
      existing=[{"title":"10 Best AI Tools to Transform Your Digital Marketing Strategy","url":blog("10-best-ai-tools-to-transform-your-digital-marketing-strategy")}],
      risk="Low", rec="Optimise Existing Article", newTopic=None,
      targetUrl=f"{E}/course/generative-ai-chatgpt-gemini-and-popular-ai-tools-course/",
      link="Refresh the AI-tools listicle (2026 tools) and link to GenAI + AI-in-Digital-Marketing courses.",
      reason="Existing article ranks #7 for 'ai tools for marketing'; a refresh + links supports the GenAI course push.",
      status="Live"),
 dict(courseId="aiess", kw="learn ai singapore", vol=1700, kd=26, intent="Informational",
      existing=[],
      risk="Low", rec="Create New Article",
      newTopic="How to Learn AI in Singapore: Beginner's Roadmap, Courses & SkillsFuture Funding (2026)",
      targetUrl=f"{E}/blog/how-to-learn-ai-in-singapore/",
      link="Link to AI Essentials (primary), Generative AI, Agentic AI and Prompt Engineering course pages with exact-match anchors.",
      reason="No existing blog content covers AI learning intent. 'ai course singapore' (1,700/mo) SERP rewards topical authority — a roadmap guide builds it without cannibalising the course page (different intent).",
      status="Proposed"),
 dict(courseId="pbi", kw="what is power bi", vol=250, kd=15, intent="Informational",
      existing=[],
      risk="Low", rec="Create New Article",
      newTopic="Power BI vs Excel: Which Should Analysts Learn First? (Singapore Guide)",
      targetUrl=f"{E}/blog/power-bi-vs-excel/",
      link="Link to WSQ Power BI course with 'Power BI course Singapore' anchor; cross-link Tableau + Data Analytics courses.",
      reason="Zero existing Power BI content while the course page has zero visibility on a 350/mo KD 0 keyword. One supporting article + on-page optimisation closes the gap.",
      status="Proposed"),
 dict(courseId="da", kw="data analyst career singapore", vol=350, kd=30, intent="Informational",
      existing=[],
      risk="Low", rec="Create New Article",
      newTopic="Data Analyst Career Guide Singapore: Salary, Skills & How to Start (2026)",
      targetUrl=f"{E}/blog/data-analyst-career-guide-singapore/",
      link="Link to Data Analytics Essentials, Power BI, Tableau courses + Data Analytics Capstone.",
      reason="KD 52 on the money keyword means Equinet needs topical authority; a career guide mirrors the successful digital-marketing-salary-guide playbook already ranking for Equinet.",
      status="Proposed"),
 dict(courseId="video", kw="video editing software comparison", vol=150, kd=5, intent="Informational",
      existing=[],
      risk="Low", rec="Create New Article",
      newTopic="CapCut vs DaVinci Resolve vs Premiere Pro: Which Video Editor Should You Learn?",
      targetUrl=f"{E}/blog/capcut-vs-davinci-resolve-vs-premiere/",
      link="Link to CapCut, DaVinci Resolve and Video Creation & Editing course pages.",
      reason="No video-related blog content exists despite 6+ video/photo courses; comparison content captures tool-choice intent and feeds the 'video editing course singapore' (250/mo KD 0) push.",
      status="Proposed"),
 dict(courseId="uxui", kw="ux designer career singapore", vol=150, kd=18, intent="Informational",
      existing=[],
      risk="Low", rec="Create New Article",
      newTopic="How to Become a UX Designer in Singapore: Skills, Portfolio & Career Switch Guide",
      targetUrl=f"{E}/blog/how-to-become-ux-designer-singapore/",
      link="Link to UX/UI Essentials (primary), Advanced UX/UI and CUXD with differentiated anchors (beginner vs advanced vs certification).",
      reason="Zero UX blog content despite a full UX course line; a career guide builds authority and clarifies which course page targets which keyword (helps the cannibalisation fix).",
      status="Proposed"),
 dict(courseId="wp", kw="website cost singapore", vol=150, kd=8, intent="Informational / Commercial",
      existing=[],
      risk="Low", rec="Create New Article",
      newTopic="How Much Does a Website Cost in Singapore? (DIY vs Agency, 2026)",
      targetUrl=f"{E}/blog/website-cost-singapore/",
      link="Link to WordPress Website Creation + CLPDS ('build it yourself with our WordPress course').",
      reason="Genuine gap; captures buyers earlier in the journey and funnels to the #2-ranking WordPress course and the web-design push.",
      status="Proposed"),
 dict(courseId="canva", kw="how to use canva", vol=250, kd=10, intent="Informational",
      existing=[],
      risk="Low", rec="Create New Article",
      newTopic="How to Use Canva: A Beginner's Step-by-Step Guide (existing ClickUp task)",
      targetUrl=f"{E}/blog/how-to-use-canva/",
      link="Link to WSQ Canva Design course with 'Canva course Singapore' anchor.",
      reason="Already planned — ClickUp task z9088242r2 exists in SEO Content View. Shown here to prevent duplicate planning.",
      status="In progress (ClickUp)"),
 dict(courseId="agentic", kw="agentic ai explained", vol=200, kd=6, intent="Informational",
      existing=[],
      risk="Low", rec="No Action",
      newTopic=None,
      targetUrl=f"{E}/course/agentic-ai-course/",
      link="Follow the existing ClickUp cluster task's internal-linking plan.",
      reason="ClickUp task 'Optimise Agentic AI SEO Cluster: Course + Existing Blogs' (z9088242xz) already covers course + supporting content. No new planning needed.",
      status="In progress (ClickUp)"),
 dict(courseId="copy", kw="copywriting vs content writing", vol=30, kd=0, intent="Informational",
      existing=[{"title":"Copywriting vs Content Writing: Key Differences","url":blog("copywriting-vs-content-writing-understanding-the-key-differences")}],
      risk="Low", rec="Optimise Existing Article", newTopic=None,
      targetUrl=f"{E}/course/copywriting-course/",
      link="Add 'copywriting course Singapore' anchor to the course page (currently #9 for 'copywriting course', declining).",
      reason="Article exists and ranks #6; interlink instead of new content to help the course page recover.",
      status="Live"),
 dict(courseId="entre", kw="entrepreneurship guides", vol=1500, kd=35, intent="Informational",
      existing=[{"title":"What is Entrepreneurship?","url":blog("what-is-entrepreneurship-the-difference-between-a-dream-and-a-business")},
                {"title":"How to Secure Funding for Your Startup in Singapore","url":blog("how-to-secure-funding-for-your-startup-business-in-singapore")},
                {"title":"7 Ways to Get a Startup Loan in Singapore","url":blog("7-ways-to-get-a-startup-loan-in-singapore-even-if-you-have-no-revenue-yet")}],
      risk="Low", rec="Optimise Existing Article", newTopic=None,
      targetUrl=f"{E}/course/entrepreneurship-course/",
      link="Add course CTAs from all 3 startup/entrepreneurship posts to the Entrepreneurship course.",
      reason="Cluster exists with rankings ('entrepreneurship' #11, 'angel investors' #1); course page just needs the internal links.",
      status="Live"),
 dict(courseId="content", kw="content marketing cluster", vol=400, kd=20, intent="Informational",
      existing=[{"title":"7 Essential Types of Content Pillars","url":blog("7-essential-types-of-content-pillars-and-how-to-use-them")},
                {"title":"What is Content Marketing (with Examples)","url":blog("what-is-content-marketing-and-why-is-it-important-with-examples")},
                {"title":"Hero Hub Hygiene Content Strategy","url":blog("hero-hub-hygiene-content-strategy-explained-a-complete-guide-with-examples")}],
      risk="Low", rec="No Action", newTopic=None,
      targetUrl=f"{E}/course/content-marketing-course/",
      link="Cluster already strong — ensure each post carries one exact-anchor link to the course page.",
      reason="Content marketing topical authority already established (4+ ranking posts). Focus effort on the course page itself.",
      status="Live"),
]
for i, c in enumerate(CONTENT):
    c["id"] = f"ct-{i+1:02d}"

# ---------- Action plan ----------
ACTIONS = []
def act(courseId, kwd, category, title, detail, objective, priority, existingTask=None):
    ACTIONS.append(dict(id=f"act-{len(ACTIONS)+1:02d}", courseId=courseId, kw=kwd, category=category,
        title=title, detail=detail, objective=objective, priority=priority,
        status="In progress (ClickUp)" if existingTask else "Not started",
        existingClickUpTask=existingTask))

act("dmhub","digital marketing course","Resolve keyword cannibalisation",
    "Recover 'digital marketing course' from #10 back to top 3",
    "Diagnose the #1→#10 drop: de-optimise the beginner's-guide blog post for course intent, re-point internal links to /digital-marketing-courses/, refresh hub content + freshness date, add course schema, and re-strengthen the SkillsFuture funding section ('digital marketing course skillsfuture' also slipped 5→8).",
    "Return the two 600-700/mo keywords to page-1 top-3; recover the single largest traffic loss on the site.","High",
    {"id":"z9088242vw","name":"Optimise Digital Marketing Foundations SEO Rankings","url":f"{CU}z9088242vw"}),
act("pbi","power bi course singapore","Optimise existing course landing page",
    "Optimise WSQ Power BI page for 'power bi course singapore' (350/mo, KD 0)",
    "Add the exact phrase to title/H1/meta, add SkillsFuture funding + course outline sections, publish the Power BI vs Excel supporting article, and internally link from data-analytics pages.",
    "Enter top 10 within 1-2 refresh cycles; top 3 medium-term (JCI at DR 7 ranks #6 today).","High"),
act("cyber","cybersecurity course singapore","Add internal links",
    "Connect the cybersecurity blog cluster to the Awareness course page",
    "Optimise the course page for 'cybersecurity course singapore' (500/mo, KD 2) + 'cybersecurity awareness training'; add in-content links + banners from the 3 ranking cyber blog posts.",
    "Break into top 10 for a 500/mo keyword the site currently has zero visibility on.","High"),
act("genai","generative ai course singapore","Optimise existing course landing page",
    "Optimise Generative AI course page (400/mo, KD 7)",
    "Rewrite title/H1/meta around 'Generative AI Course Singapore', add ChatGPT-specific FAQ (captures 'chatgpt course singapore', 150/mo KD 0), refresh the AI-tools blog post and link it in.",
    "Page-1 entry; Vertical Institute (DR 40) at #2 proves DR 41 can compete.","High"),
act("seo","seo course singapore","Update title/H1/meta description",
    "Push SEO course page from #5 to top 3",
    "Refresh title/meta CTR (funding % + 'AEO/GEO' differentiator), add FAQ + review schema, verify legacy /course/seo-training-course/ canonicalises to the main page, add exact-anchor links from SEO vs SEM + SEO packages articles.",
    "Top 3 for 'seo course singapore' (250/mo); defend #1 'seo courses singapore' and #2 'seo training singapore'.","High"),
act("uxui","ux ui / ui ux design course","Resolve keyword cannibalisation",
    "Consolidate the UX/UI keyword cluster across 4 competing pages",
    "Assign: Essentials page → 'ui ux course singapore / ux design course singapore'; Advanced → 'advanced ux ui'; CUXD → certification intent; hub → category terms. Fix titles/anchors accordingly; the Advanced page currently outranks Essentials for beginner keywords.",
    "Stop 4 pages splitting relevance across 8 UX keywords sitting at #5-#9; lift the cluster into top 3-5.","High"),
act("aiess","ai course singapore","Improve topical authority",
    "Build the AI topical cluster around AI Essentials (1,700/mo)",
    "Optimise AI Essentials page, publish the 'How to Learn AI in Singapore' roadmap article, interlink all AI course pages (GenAI, Agentic, Prompt Engineering, AI in DM) into a hub-and-spoke.",
    "Enter top 10 for the highest-volume keyword in the portfolio; feed the whole AI course line.","High"),
act("prompt","prompt engineering course singapore","Optimise existing course landing page",
    "Optimise Prompt Engineering page (300 + 350/mo variants)",
    "Add 'Singapore' + SkillsFuture phrasing to title/H1/meta, expand outline, link from the AI cluster pages and the AI-tools article.",
    "Page-1 entry on both variants (KD 18 global, uncached SG SERP = low local competition).","High"),
act("tiktok","tiktok course singapore","Optimise existing course landing page",
    "Lift TikTok Marketing page from #6 to top 3",
    "Execute the existing ClickUp task: refresh content for striking-distance keywords, add 'tiktok marketing course' (150/mo) exact phrase, add review schema, link from both TikTok blog posts.",
    "Top 3 on 'tiktok course singapore'; capture the uncovered 150/mo variant.","High",
    {"id":"z9088242uk","name":"Optimise TikTok Marketing Skills Content for Striking-Distance Rankings","url":f"{CU}z9088242uk"}),
act("agentic","agentic ai course","Improve topical authority",
    "Execute Agentic AI SEO cluster (existing ClickUp task)",
    "Course page + existing blog optimisation per the existing ClickUp task; monitor the fast-growing 200/mo keyword.",
    "First-page entry while the SERP is still young (KD 6).","High",
    {"id":"z9088242xz","name":"Optimise Agentic AI SEO Cluster: Course + Existing Blogs","url":f"{CU}z9088242xz"}),
act("clpds","web design course singapore","Expand or rewrite content",
    "Target 'web design course singapore' (150/mo, KD 0) with CLPDS page",
    "Improved 12→10 organically — add a 'web design course' content block, align H2s, resolve overlap with WSQ Landing Page Design + WordPress pages, add internal links from design hub.",
    "Top 5 on both 'web design course singapore' and 'website design course singapore' (100/mo, slipped 8→10).","Medium"),
act("video","video editing course singapore","Optimise existing course landing page",
    "Optimise video editing course line for 'video editing course singapore' (250/mo, KD 0)",
    "Pick the Video Creation & Editing page as target, add exact phrasing + course-line links (CapCut, DaVinci, Certified Video Editor), publish the editor-comparison article.",
    "Top 10 entry (DR 13 sites rank today), then top 5.","Medium"),
act("tableau","tableau course singapore","Optimise existing course landing page",
    "Optimise Tableau page for 'tableau course singapore' (150/mo, KD 0)",
    "Exact phrase in title/H1/meta, SkillsFuture section, internal links from Power BI + Data Analytics pages.",
    "Top 10 entry (JCI at DR 7 ranks #8).","Medium"),
act("da","data analytics course singapore","Improve topical authority",
    "Build data-analytics authority (KD 52 head term)",
    "Optimise Data Analytics Essentials page, publish Data Analyst Career Guide, target 'business analytics course singapore' (150/mo, KD 2) as the quick win, interlink Power BI/Tableau/Capstone.",
    "Quick win on business-analytics variant; 12-month path on the KD 52 head term.","Medium"),
act("smm","social media course","Optimise existing course landing page",
    "Lift Social Media Marketing page from #6 to top 3",
    "Title/meta refresh with funding hook, add 'social media marketing course' exact phrase (150/mo — currently not captured), FAQ + review schema, links from the 5-post social media blog cluster.",
    "Top 3 on 'social media course'; capture the uncovered exact-match variant.","Medium"),
act("gads","google ads course","Expand or rewrite content",
    "Push Google Ads page from #8 and capture the Singapore variant",
    "Add 'google ads course singapore' (150/mo) phrasing, expand outline vs Ask Training's #5 page, link from what-is-CPC + digital-advertising articles.",
    "Top 5 among non-Google results on both variants.","Medium"),
act("ga4","google analytics course singapore","Update title/H1/meta description",
    "Reclaim top 3 for GA4 course (slipped 3→4)",
    "Title/meta refresh, add 'GA4 course' phrasing (100/mo uncaptured), refresh GA4-certification article and its internal link.",
    "Back to top 3; capture 'ga4 course'.","Medium"),
act("ecom","ecommerce course singapore","Add internal links",
    "Take #1 for 'ecommerce course singapore' (improved 4→3)",
    "Add exact-anchor internal links from the 4-post ecommerce blog cluster, add review schema; Tertiary Courses #1 is a thin category page.",
    "#1 on 150/mo KD 0 keyword; hold #5 'ecommerce course'.","Medium"),
act("content","content marketing singapore","Optimise existing course landing page",
    "Push Content Marketing course from #5 to top 3",
    "Only course-type result near the top of a mixed-intent SERP — strengthen relevance (title/H1), add case studies, exact-anchor links from the content-marketing blog cluster.",
    "Top 3 on 300/mo KD 2 keyword.","Medium"),
act("dx","digital transformation course singapore","Update title/H1/meta description",
    "Capture the 150/mo Singapore variant (page already rising: 7→3 on 'digital transformation courses')",
    "Add exact local phrasing to title/meta; keep momentum with content freshness.",
    "Page 1 on all three DX variants.","Medium"),
act("canva","canva course singapore","Update title/H1/meta description",
    "Capture 'canva course singapore' (100/mo) + lift 'canva course' from #6",
    "Add 'Singapore' phrasing, publish the planned How-to-Use-Canva guide (existing ClickUp task) and link it in.",
    "Top 3 on both Canva variants.","Medium",
    {"id":"z9088242r2","name":"How to Use Canva: A Beginner's Step-by-Step Guide","url":f"{CU}z9088242r2"}),
act("copy","copywriting course","Expand or rewrite content",
    "Recover 'copywriting course' (7→9) while defending top-3 variants",
    "Content refresh + internal links from copywriting-vs-content-writing article; keep #2/#3 on Singapore variants.",
    "Back to top 5 on 'copywriting course'; #1 on 'copywriting courses singapore'.","Medium"),
act("dmf","fundamentals of digital marketing","Expand or rewrite content",
    "Recover Foundations page decline (4→9 / 3→6)",
    "Refresh course page, align with hub fix, assign 'wsq digital marketing course' (100/mo) targeting.",
    "Back to top 5 on fundamentals keywords.","Medium"),
act("meta","facebook ads course","Add relevant sections",
    "Add Facebook Ads section to Meta Marketing page",
    "Capture 'facebook ads course' (70/mo, KD 26) with a dedicated ads-module section; defend #4 'facebook marketing course'.",
    "Rank both Meta keywords top 5.","Low"),
act("wp","wordpress course","Monitor ranking",
    "Defend #2 'wordpress course' (slipped from #1)",
    "Monitor weekly; the #1 is learn.wordpress.org (navigational). Keep content fresh; publish website-cost article for supporting links.",
    "Hold #2-#3; #1 among commercial results.","Low"),
act("dcc","content creation course","Monitor ranking",
    "Push 'content creation course' from #2 to #1",
    "Improved 4→2; add review schema + internal link from content-creation blog post, then monitor.",
    "#1 on 250/mo KD 0 keyword.","Low"),
act("photo","photography course singapore","Optimise existing course landing page",
    "Give the photography course line a rankable target page",
    "Optimise Photography Essentials page (or a category hub) for 'photography course singapore' (200/mo, KD 4).",
    "Top 10 entry for the photography line.","Low"),
act("pubspeak","public speaking course singapore","Optimise existing course landing page",
    "Optimise Public Speaking page (300/mo, KD 11)",
    "Exact phrase in title/H1/meta; presentation-skills variant (80/mo KD 0) on the Presentation Design page.",
    "Top 10 entry.","Low"),
act("entre","entrepreneurship course singapore","Add internal links",
    "Link entrepreneurship blog cluster to the course page (150/mo, KD 0)",
    "Course CTAs from the 3 startup posts; optimise course page title.",
    "Top 10 entry.","Low"),
act("figma","figma course singapore","Update title/H1/meta description",
    "Make the WTF course findable for 'figma course singapore' (60/mo)",
    "The course title 'What The Figma' obscures the keyword — add plain 'Figma Course Singapore' phrasing to title/meta.",
    "Top 10 entry.","Low"),
act("email","email marketing course singapore","Update title/H1/meta description",
    "Optimise Email Marketing page (90/mo variant uncaptured)",
    "Exact phrase in title/H1/meta; internal link from email-subject-lines article.",
    "Top 10 entry.","Low"),
act("seo","backlinks","Build backlinks",
    "Backlink programme for money pages (DR 41 vs SMU DR 79)",
    "Digital-PR and partner links to /digital-marketing-courses/, SEO, Power BI, GenAI and Cybersecurity course pages — the DR gap is the main brake on institution-dominated SERPs.",
    "Close the authority gap enough to hold top-3 positions once won.","Medium"),

data = {
  "meta": {
    "generated": SNAPSHOT, "baseline": BASELINE, "country": "Singapore (Google SG)",
    "site": E, "clickup": {"listId": "901814205053", "listName": "all-courses-iqa (SEO Content View)",
      "viewUrl": "https://app.clickup.com/90181914545/v/li/901814205053", "teamId": "90181914545"},
    "sources": "Ahrefs (organic keywords, Keywords Explorer, SERP overview) pulled 2026-08-14; previous ranks = Ahrefs 2026-07-14 comparison; ClickUp SEO Content View parent tasks fetched 2026-08-14."
  },
  "courses": [dict(id=i, name=n, url=u, clickupParentId=cid, clickupParentName=cn) for (i,n,u,cid,cn) in courses],
  "keywords": K,
  "content": CONTENT,
  "actions": ACTIONS,
}

os.makedirs("data/snapshots", exist_ok=True)
with open("data/seo-data.json","w") as f:
    json.dump(data, f, indent=1, ensure_ascii=False)
with open("data/seo-data.js","w") as f:
    f.write("window.SEO_DATA = ")
    json.dump(data, f, ensure_ascii=False)
    f.write(";\n")
snap = {"date": SNAPSHOT, "ranks": {k["kw"]: k["rank"] for k in K}}
with open(f"data/snapshots/{SNAPSHOT}.json","w") as f:
    json.dump(snap, f, indent=1, ensure_ascii=False)
base = {"date": BASELINE, "ranks": {k["kw"]: k["prevRank"] for k in K}}
with open(f"data/snapshots/{BASELINE}.json","w") as f:
    json.dump(base, f, indent=1, ensure_ascii=False)
print("courses", len(data["courses"]), "| keywords", len(K), "| content", len(CONTENT), "| actions", len(ACTIONS))
