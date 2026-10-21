# Alireza Tahani

**Email:** alireza.tahani01@gmail.com

## Professional Summary

Senior full-stack engineer (9+ years) shipping TypeScript, React, and Node.js in fintech and high-traffic SaaS. Strongest on structured data, schema validation, and real-time systems. Uses Cursor and Claude daily for review, refactors, and prompts. Built a LangGraph job assistant with Claude API structured outputs.

## Core Competencies

- TypeScript, JavaScript, React, Next.js, Node.js, Express
- Structured data: Zod, schema validation, REST APIs, GraphQL
- Claude API, Cursor, LangGraph, Pydantic structured outputs
- State: Redux, Redux-Saga, Zustand, React Query
- Real-time systems (Socket.io, live market data), React Query caching/retries
- Performance (Lighthouse / Web Vitals), Docker, CI/CD, Git
- Independent delivery across startups and freelance clients

## Experience

### Lead FrontEnd Developer — SAP (Germany) / Identity Global (UK) | May 2023 – Present

- Led 3 front-end engineers on architecture, code quality, and delivery for a trading platform.
- Technical lead on the trading UI: coding standards, architecture, and performance strategy.
- Built spot and futures interfaces with 200ms live market data refresh and no UI stalls under load.
- Designed client-side data pipelines with Web Workers, cutting main-thread blocking by 70% for charts and order books.
- Shipped structured validation with React Hook Form + Zod so invalid payloads fail before they hit downstream trading systems (40% fewer submission errors).
- Partnered with backend on real-time trading APIs: contracts, retries, caching, and fault-tolerant refresh for live financial data.
- Delivered 90+ Lighthouse scores on trading pages (FCP 0.7s, LCP 0.9s, CLS 0.006, Speed Index 1.2s).
- Strict TypeScript, feature modules, shared UI primitives, and API abstraction layers.
- Containerized the front-end stack with Docker.

### FrontEnd Developer — Preezma, Yerevan | May 2021 – May 2023

- Built React + Redux-Saga + REST features that lifted engagement 30% and revenue 10%.
- Cut load time ~50% by removing performance bottlenecks.
- Shipped work across 4 product teams; refined 40+ requirements for parallel iOS/Android.
- Automated mobile CI/CD, cutting release time 5×.
- TDD with Jest and Enzyme; ~95% coverage on core modules.

### FrontEnd Developer — Fixefy.io | May 2020 – May 2021

- Shared UI component layer that cut build time 40% and aligned the design language.
- Worked with backend on front-end/server contracts; API response time dropped ~20%.
- 95% on-time feature delivery on tight timelines.
- Reworked data-heavy views, cutting HTTP requests 80%.
- React, Redux, Router; Jira-based sprint planning.

### FrontEnd Developer — Multiple Startups & Enterprise Clients, Tehran | 2016 – 2021

- End-to-end product work in an Agile team of 10; 30+ commercial front-ends.
- React, Next.js, Redux, Webpack micro-frontends, Jenkins CI/CD.
- Custom UI library and Google Maps / IoT visualizations.
- Semantic HTML and accessibility (ADA-oriented) on client sites.

## Relevant Projects

### Job Assistant — personal, 2026

GitHub: https://github.com/alirezatahani0/job-hunter

- LangGraph pipeline: fetch remote jobs, rank against a CV, tailor a resume with **one Claude API call**, local ATS keyword/format check, Word export.
- Production-style LLM wiring: Anthropic Claude (Haiku), structured JSON → Pydantic models, schema coercion when the model uses alternate field names, fail-closed validation.
- Stack: Python, LangGraph, Claude API, vanilla JS UI.
