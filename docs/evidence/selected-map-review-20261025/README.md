# Selected-route map review (T52)

D's50f06a3 removes the unmodelled Northern line and adds actual-endpoint fallback
for supported routes without a stop list. Review found a CSS selector leak:
map labels inherited7px stroke and fill:none. This integration separates the
route-line rule from text, restoring ink fill and no stroke on labels.

[Actual frozen-API Chrome checks](browser-checks.json) verify both supported
bus29 origins, no Northern line/timing bars, all text bounding boxes inside the
SVG, readable label styles, zero page errors and the locked16:22 recommendation.
Visual review: [Mornington](mornington.png), [Finsbury](finsbury.png).
These checks used50f06a3 plus this PR's CSS selector fix.62frontend tests and build
pass. No backend/model/default/data change; arrivals remain inferred/preliminary.
The existing backup video records the older UI style and remains labelled by its
source version; it is not a newly recorded video of this layout.
