"use strict";
const library = window.SPELL_LIBRARY;
const spells = library.spells;
const search = document.getElementById("search");
const guild = document.getElementById("guild");
const type = document.getElementById("type");
const dialog = document.getElementById("spell-dialog");
let selectedButton = null;

function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function badges(spell) {
  const tags = element("div", undefined, "tags");
  for (const g of spell.guilds) tags.append(element("span", g, "badge guild-" + g.toLowerCase()));
  tags.append(element("span", spell.type === "Miscellaneous" ? "Misc" : spell.type, "badge type-" + spell.type.toLowerCase()));
  return tags;
}
function render() {
  const tokens = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const matches = spells.filter(spell => {
    const haystack = [spell.name, spell.abbreviation, spell.type, ...spell.guilds].join(" ").toLowerCase();
    return (!guild.value || spell.guilds.includes(guild.value)) && (!type.value || spell.type === type.value) && tokens.every(token => haystack.includes(token));
  });
  const list = document.getElementById("spells");
  list.replaceChildren();
  document.getElementById("count").textContent = matches.length === spells.length ? spells.length : matches.length + " / " + spells.length;
  document.getElementById("empty").hidden = matches.length > 0;
  for (const spell of matches) {
    const item = element("li");
    const button = element("button", undefined, "spell-row");
    button.type = "button";
    const heading = element("div", undefined, "spell-heading");
    heading.append(element("span", spell.name, "spell-name"), element("span", spell.abbreviation || "—", "spell-abbreviation"));
    button.append(heading, badges(spell));
    button.addEventListener("click", () => showSpell(spell, button));
    item.append(button);
    list.append(item);
  }
}
function section(title, text) {
  const box = element("section", undefined, "detail-section");
  box.append(element("h2", title), element("p", text));
  return box;
}
function article(html) {
  // This is bundled, allowlist-sanitized wiki content, never a bridge payload.
  const box = element("div", undefined, "details-article");
  box.innerHTML = html;
  return box;
}
function sourceLink(label, url) {
  const link = element("a", label);
  link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer";
  return link;
}
function showSpell(spell, button) {
  selectedButton = button;
  document.getElementById("detail-title").textContent = spell.name;
  document.getElementById("detail-tags").replaceChildren(...badges(spell).children, element("span", spell.abbreviation || "No abbreviation documented", "badge"));
  const content = document.getElementById("detail-content");
  content.replaceChildren(element("p", spell.description || spell.facts.Description || "", "detail-summary"));
  const metrics = element("dl", undefined, "metrics");
  for (const [name, value] of [["GP", spell.gp], ["Size / mind space", spell.size], ["Thaums", spell.facts.Thaums], ["Extra target GP", spell.extra_target_gp || "—"], ["Size / GP", spell.efficiency], ["Guild", spell.guilds.join(" & ")]]) {
    const cell = element("div", undefined, "metric");
    cell.append(element("dt", name), element("dd", value || "Not documented")); metrics.append(cell);
  }
  content.append(metrics, section("Components", spell.components || spell.facts.Components || "Not documented"));
  const learn = section("Where to learn", (spell.tomes || []).map(book => book.name).join("; ") || spell.acquisition || "See the acquisition details in the spell article below.");
  for (const book of spell.learning) {
    const details = element("details");
    details.append(element("summary", book.name + " — book details & locations"), article(book.article));
    learn.append(details);
  }
  if (spell.tomes && spell.acquisition) learn.append(element("p", spell.acquisition));
  if (spell.crystals && spell.crystals.length) learn.append(element("p", "Crystal: " + spell.crystals.map(c => c.name).join(", ")));
  content.append(learn);
  content.append(section("Required skills / casting stages", spell.skills.length ? spell.skills.map((skill, i) => (i + 1) + ". " + skill).join("\n") : "See the Skills section in the full article below."));
  const bonus = section("Suggested bonuses", spell.bonuses.length ? "Approximate bonus where the wiki’s spellcheck/focus-tea chart turns fully green. These are chart estimates, not guaranteed success or minimum learning levels. Required skills and any further recommendations are in the full details below." : "No colored bonus chart is documented in this backup. See the Skills section and spell notes below for any written recommendations.");
  if (spell.bonuses.length) {
    const table = element("table", undefined, "bonus-table");
    const head = element("tr"); head.append(element("th", "Stage / skill"), element("th", "Green from")); table.append(head);
    for (const [i, b] of spell.bonuses.entries()) {
      const row = element("tr"); row.append(element("td", (i + 1) + ". " + b.skill), element("td", "≈ " + b.green_from)); table.append(row);
    }
    bonus.append(table);
  }
  content.append(bonus);
  // Preserve every documented infobox fact, including less common properties.
  const facts = element("details"); facts.append(element("summary", "All spell facts"));
  const dl = element("dl");
  for (const [key,value] of Object.entries(spell.facts)) dl.append(element("dt", key), element("dd", value || "Not documented"));
  facts.append(dl); content.append(facts);
  const full = element("section", undefined, "detail-section");
  full.append(element("h2", "Full spell details"), article(spell.article)); content.append(full);
  const footer = element("footer", undefined, "hint source-note");
  footer.append(sourceLink("Discworld MUD Wiki · source & contributors", spell.source), element("p", spell.modified)); content.append(footer);
  dialog.showModal();
  content.scrollTop = 0;
  document.getElementById("close-detail").focus();
}
document.getElementById("close-detail").addEventListener("click", () => dialog.close());
dialog.addEventListener("close", () => { if (selectedButton && selectedButton.isConnected) selectedButton.focus(); });
dialog.addEventListener("click", event => { if (event.target === dialog) { const r=dialog.getBoundingClientRect(); if (event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom) dialog.close(); } });
search.addEventListener("input", render);
guild.addEventListener("change", render);
type.addEventListener("change", render);
document.getElementById("clear-search").addEventListener("click", () => { search.value=""; render(); search.focus(); });
render();
