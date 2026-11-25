import { describe, expect, it } from "vitest";
import { monitor } from "./fixture.monitor";
import { GUIDE_TITLE, guideTitles, headers, pageLabel, qtyText, SHEET_TITLE, stepTitle } from "./pages";
import { DENSE_TABLE_ROWS, tableClass } from "./render";

describe("page titles and numbers", () => {
  it("guide: a title page and one page per step, numbered 1..8 of 8", () => {
    const titles = guideTitles(monitor);
    expect(titles).toHaveLength(8);
    expect(titles[0]).toBe(GUIDE_TITLE);
    expect(titles[1]).toBe("Step 1 of 7: Set the inserts in the pod");
    expect(titles[7]).toBe("Step 7 of 7: Fit the clamp screw");
    const heads = headers(monitor, titles);
    expect(heads.map((h) => h.page)).toEqual([1, 2, 3, 4, 5, 6, 7, 8].map((n) => `page ${n} of 8`));
    for (const h of heads) {
      expect(h.project).toBe("Monitor weather display");
      expect(h.version).toBe("v0p9");
    }
    expect(heads[3].title).toBe(stepTitle(monitor, 2));
  });

  it("sheet: one page, page 1 of 1", () => {
    expect(headers(monitor, [SHEET_TITLE])).toEqual([
      { project: "Monitor weather display", version: "v0p9", title: SHEET_TITLE, page: "page 1 of 1" },
    ]);
  });

  it("formats labels and quantities", () => {
    expect(pageLabel(2, 5)).toBe("page 2 of 5");
    expect(qtyText(3)).toBe("3 x");
    expect(qtyText(0)).toBe("-");
  });
});

describe("parts table density", () => {
  it("the monitor display's 13 rows use the normal table; a longer list is set smaller to stay on its page", () => {
    expect(monitor.table).toHaveLength(13);
    expect(tableClass(monitor.table.length)).toBe("pr-table");
    expect(tableClass(DENSE_TABLE_ROWS)).toBe("pr-table");
    expect(tableClass(DENSE_TABLE_ROWS + 1)).toBe("pr-table pr-table-dense");
  });
});
