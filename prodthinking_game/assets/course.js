/* Product Thinking course: shared interactive components.
 *
 * [data-quiz]     A group of <fieldset class="q" data-answer="N"> questions. Each has
 *                 .opt buttons and an optional hidden .explain (with a .verdict span).
 *                 Optional [data-score] shows "right / total"; optional [data-reset] clears it.
 *
 * [data-rewrite]  A textarea + [data-check] button. Flags words from data-flags (comma list)
 *                 that signal a solution in disguise, then opens the .model <details>.
 *
 * [data-order]    Click-to-sequence exercise. .chip buttons carry data-pos (1-based correct
 *                 position) and move into the .order-slots list; [data-check] grades the
 *                 sequence into .order-out; [data-reset] returns every chip to .order-pool.
 *
 * [data-whys]     A why-ladder: [data-add] appends a "Why?" text input (up to data-max).
 *                 Once data-reveal-after inputs are filled, .whys-check (self-check) appears.
 */
(function () {
  function initQuiz(group) {
    var qs = Array.prototype.slice.call(group.querySelectorAll(".q"));
    var score = group.querySelector("[data-score]");

    function update() {
      if (!score) return;
      var right = group.querySelectorAll(".q.got-it").length;
      var done = group.querySelectorAll(".q.got-it, .q.missed").length;
      score.textContent = right + " / " + qs.length + (done === qs.length ? " · done" : "");
    }

    qs.forEach(function (q) {
      var answer = Number(q.dataset.answer);
      var opts = Array.prototype.slice.call(q.querySelectorAll(".opt"));
      var explain = q.querySelector(".explain");
      opts.forEach(function (btn, i) {
        btn.type = "button";
        btn.addEventListener("click", function () {
          if (q.classList.contains("got-it") || q.classList.contains("missed")) return;
          var ok = i === answer;
          btn.classList.add(ok ? "is-right" : "is-wrong");
          if (opts[answer]) opts[answer].classList.add("is-right");
          opts.forEach(function (o) { o.disabled = true; o.setAttribute("aria-pressed", String(o === btn)); });
          q.classList.add(ok ? "got-it" : "missed");
          if (explain) {
            var v = explain.querySelector(".verdict");
            if (v) v.textContent = ok ? "Right." : "Not quite.";
            explain.hidden = false;
          }
          update();
        });
      });
    });

    var reset = group.querySelector("[data-reset]");
    if (reset) {
      reset.addEventListener("click", function () {
        qs.forEach(function (q) {
          q.classList.remove("got-it", "missed");
          q.querySelectorAll(".opt").forEach(function (o) {
            o.disabled = false;
            o.classList.remove("is-right", "is-wrong");
            o.removeAttribute("aria-pressed");
          });
          var ex = q.querySelector(".explain");
          if (ex) ex.hidden = true;
        });
        update();
      });
    }
    update();
  }

  function initRewrite(box) {
    var area = box.querySelector("textarea");
    var check = box.querySelector("[data-check]");
    var out = box.querySelector(".rw-out");
    var model = box.querySelector(".model");
    var flags = (box.dataset.flags || "").split(",").map(function (s) { return s.trim().toLowerCase(); }).filter(Boolean);

    check.addEventListener("click", function () {
      var text = area.value.trim();
      var words = text.toLowerCase().match(/[a-z]+/g) || [];
      out.hidden = false;
      out.className = "rw-out";
      if (!text) {
        out.classList.add("empty");
        out.textContent = "Write a sentence first, then check it.";
        return;
      }
      var hits = flags.filter(function (f) { return words.indexOf(f) !== -1; });
      if (hits.length) {
        out.classList.add("flag");
        out.textContent = "This still names a solution: " + hits.join(", ") +
          ". Describe what goes wrong for people instead, and leave the fix out.";
      } else if (words.length < 10) {
        out.classList.add("flag");
        out.textContent = "No solution named, which is good. It is short, though: say who is affected and how you know.";
      } else {
        out.classList.add("ok");
        out.textContent = "No solution named. Now compare it with the model answer and tick the checklist yourself.";
      }
      if (model) model.open = true;
    });
  }

  function initOrder(box) {
    var slots = box.querySelector(".order-slots");
    var pool = box.querySelector(".order-pool");
    var out = box.querySelector(".order-out");
    var chips = Array.prototype.slice.call(pool.querySelectorAll(".chip"));

    function clearMarks() {
      slots.querySelectorAll("li").forEach(function (li) { li.classList.remove("is-right", "is-wrong"); });
      out.hidden = true;
    }
    chips.forEach(function (chip) {
      chip.type = "button";
      chip.addEventListener("click", function () {
        var li = document.createElement("li");
        li.textContent = chip.textContent;
        li.dataset.pos = chip.dataset.pos;
        li.tabIndex = 0;
        li.title = "Click to take this step back out";
        function back() { li.remove(); chip.hidden = false; clearMarks(); }
        li.addEventListener("click", back);
        li.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); back(); } });
        slots.appendChild(li);
        chip.hidden = true;
        clearMarks();
      });
    });
    box.querySelector("[data-check]").addEventListener("click", function () {
      var placed = Array.prototype.slice.call(slots.querySelectorAll("li"));
      out.hidden = false;
      if (placed.length < chips.length) {
        out.textContent = "Place all " + chips.length + " causes first (" + placed.length + " placed).";
        return;
      }
      var right = 0;
      placed.forEach(function (li, i) {
        var ok = Number(li.dataset.pos) === i + 1;
        if (ok) right++;
        li.classList.add(ok ? "is-right" : "is-wrong");
      });
      out.textContent = right === placed.length
        ? "All " + right + " in order. Each answer explains the one above it."
        : right + " of " + placed.length + " in the right place. Read each pair aloud: does the lower line answer “why?” for the line above? Click a step to take it back out.";
    });
    box.querySelector("[data-reset]").addEventListener("click", function () {
      slots.innerHTML = "";
      chips.forEach(function (c) { c.hidden = false; });
      out.hidden = true;
    });
  }

  function initWhys(box) {
    var list = box.querySelector(".whys-list");
    var add = box.querySelector("[data-add]");
    var check = box.querySelector(".whys-check");
    var max = Number(box.dataset.max || 7);
    var revealAfter = Number(box.dataset.revealAfter || 3);
    var base = box.dataset.id || "why";

    function filled() {
      return Array.prototype.slice.call(list.querySelectorAll("input")).filter(function (i) { return i.value.trim(); }).length;
    }
    function refresh() {
      if (check && filled() >= revealAfter) check.hidden = false;
      var n = list.querySelectorAll("input").length;
      add.disabled = n >= max;
      add.textContent = n >= max ? "That’s deep enough" : (n === 0 ? "Ask why" : "Ask why again");
    }
    add.type = "button";
    add.addEventListener("click", function () {
      var n = list.querySelectorAll("input").length + 1;
      var label = document.createElement("label");
      var input = document.createElement("input");
      input.type = "text";
      input.id = base + "-" + n;
      label.htmlFor = input.id;
      label.textContent = "Why " + n + "?";
      input.placeholder = "Because…";
      input.addEventListener("input", refresh);
      list.appendChild(label);
      list.appendChild(input);
      input.focus();
      refresh();
    });
    refresh();
  }

  function boot() {
    document.querySelectorAll("[data-quiz]").forEach(initQuiz);
    document.querySelectorAll("[data-rewrite]").forEach(initRewrite);
    document.querySelectorAll("[data-order]").forEach(initOrder);
    document.querySelectorAll("[data-whys]").forEach(initWhys);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
