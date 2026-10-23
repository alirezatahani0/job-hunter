# Answers for open application questions

Written in Alireza's voice from the CV. Reuse the matching answer when a later form asks the same kind of question. Facts that are already fixed: Sofia, Bulgaria; expected salary 85000 USD; LinkedIn https://www.linkedin.com/in/alirezatahani; GitHub https://github.com/alirezatahani0.

## Why this company

I've spent the last few years on a trading screen where the numbers are someone's money, and they still have to be right while the market is moving. Tether is that same problem, just at a size I haven't worked at. People use USDT to actually move money, so the product has to be quiet and reliable. That's the kind of frontend work I want to keep doing.

## Complex state, including cross-platform

I keep two kinds of state apart. React Query holds what came from the server, like live prices, with a short cache and a retry when a tick drops. Zustand or Redux holds what the person is in the middle of, like an order they haven't sent. Charts and the order book run in a Web Worker, because that work used to freeze the page. When the same flow also has to exist on iOS and Android, I write the checks once with Zod. A bad payload fails the same way on every client, before it ever reaches the trading API.

## Code quality across a team

I led three frontend engineers on this, so it had to be simple enough that people would actually follow it. Strict TypeScript, small feature folders, and a review on every change. Jest covers the logic we can't afford to break. CI runs the tests and the typecheck before merge. We also keep one set of shared UI pieces, so nobody rebuilds the same button with slightly different spacing.

## Staying current, and a recent improvement

I don't keep a reading list. If something looks useful I try it on a branch that week. Day to day I use Cursor and Claude to look over a diff or try a refactor before I commit to it. The change I'm happiest with lately is moving the chart and order-book work into Web Workers. The main thread stopped blocking, by about 70%, and the UI quit hitching when the market got busy.

## One frontend from brief to production, and who owned it

The trading UI at Identity Global. Spot and futures, with live market data.

Mine: I took it from the brief to the screens people trade on, and I stayed on it after launch. I set the architecture, the TypeScript standards, and the performance bar. I built the spot and futures interfaces, moved charts and the order book into Web Workers, and added Zod checks so a bad order fails before it reaches the trading API. After launch the refresh stayed at 200ms without the page stalling, and the trading pages stayed at Lighthouse 90+.

The team's: three frontend engineers shipped inside that structure, in feature modules and shared UI. Backend owned the trading API. I worked with them on the contracts, retries, caching, and a refresh that keeps going when a tick drops.

The agents': Cursor and Claude help me review a diff or try a refactor before I commit to it. I read what they suggest, and I decide what ships. They do not own the screen.

## A tight deadline

At Fixefy we had a heavy screen that was going to miss its date. It was asking the server for far too much. I cut the requests by about 80%, left the information people actually used, and dropped the extra filters to the next release. It shipped in the sprint. That year we were landing about 95% of features on time, and this was one of the ones that almost didn't.
