import { registry } from "@web/core/registry";
import { CcAction } from "@community_communication/owl/cc_action";
import { POLL_CATEGORIES, audienceLabel, labelOf, m2mIds, stripHtml } from "@community_communication/owl/utils";

const FIELDS = [
    "question", "description", "category", "response_type", "anonymous", "one_per_unit",
    "state", "audience_type", "community_id", "date_start", "date_end", "option_ids",
    "participant_count", "response_rate", "author_id", "building_ids", "audience_group_ids",
];

export class CommunityPolls extends CcAction {
    static template = "community_communication.Polls";

    get categories() {
        return POLL_CATEGORIES;
    }

    get tabs() {
        return [
            { id: "all", label: "All Polls" },
            { id: "active", label: "Active" },
            { id: "scheduled", label: "Scheduled" },
            { id: "closed", label: "Closed" },
        ];
    }

    emptyForm() {
        return {
            question: "",
            description: "",
            category: "events",
            response_type: "single",
            anonymous: true,
            one_per_unit: true,
            audience_type: "community",
            community_id: this.defaultCommunityId(),
            date_start: "",
            date_end: "",
            options: ["", ""],
            building_ids: [],
            audience_group_ids: [],
            buildingQuery: "",
            groupQuery: "",
        };
    }

    setMode(mode, resId = false, extra = {}) {
        if (mode === "create" && extra.form === undefined) {
            extra = { ...extra, form: this.emptyForm() };
        }
        return super.setMode(mode, resId, extra);
    }

    async load() {
        await this.loadKpis("community.communication.poll");
        if (this.state.mode === "list") {
            await this.loadList();
        } else if (this.state.mode === "create" || this.state.mode === "edit") {
            if (this.state.mode === "create" && !this.state.form.question) {
                this.state.form = this.emptyForm();
            }
            if (this.state.mode === "edit" && this.state.resId) {
                await this.loadRecord(this.state.resId);
                this.state.form = await this.formFromRecord(this.state.record);
            }
        } else if (this.state.resId) {
            this.state.extras.vote = await this.call(
                "community.communication.poll",
                "get_vote_payload",
                [this.state.resId]
            );
            this.state.extras.selected = this.state.extras.selected || [];
            if (this.state.mode === "detail") {
                const showResults = this.state.isOfficer
                    || this.state.extras.vote.has_voted
                    || this.state.extras.vote.state !== "active";
                this.state.mode = showResults ? "results" : "vote";
            }
        }
    }

    async loadList() {
        const domain = this.listDomain();
        this.state.total = await this.orm.searchCount("community.communication.poll", domain);
        this.state.records = await this.orm.searchRead(
            "community.communication.poll",
            domain,
            FIELDS,
            {
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
                order: "date_start desc, id desc",
            }
        );
    }

    listDomain() {
        const domain = this.domainIlike("question");
        if (["active", "scheduled", "closed"].includes(this.state.filter)) {
            domain.push(["state", "=", this.state.filter]);
        }
        if (this.state.category) {
            domain.push(["category", "=", this.state.category]);
        }
        if (this.state.audience) {
            domain.push(["audience_type", "=", this.state.audience]);
        }
        return domain;
    }

    async loadRecord(id) {
        const rows = await this.orm.searchRead("community.communication.poll", [["id", "=", id]], FIELDS);
        this.state.record = rows[0] || null;
        if (this.state.record?.option_ids?.length) {
            this.state.extras.options = await this.orm.searchRead(
                "community.communication.poll.option",
                [["id", "in", this.state.record.option_ids]],
                ["name", "sequence", "vote_count", "vote_percent"]
            );
        } else {
            this.state.extras.options = [];
        }
    }

    async formFromRecord(rec) {
        const options = rec.option_ids?.length
            ? await this.orm.searchRead(
                "community.communication.poll.option",
                [["id", "in", rec.option_ids]],
                ["name"]
            )
            : [];
        return {
            question: rec.question || "",
            description: rec.description || "",
            category: rec.category,
            response_type: rec.response_type,
            anonymous: rec.anonymous,
            one_per_unit: rec.one_per_unit,
            audience_type: rec.audience_type,
            community_id: this.m2oId(rec.community_id),
            date_start: this.toDatetimeLocal(rec.date_start),
            date_end: this.toDatetimeLocal(rec.date_end),
            options: options.map((o) => o.name).concat(["", ""]).slice(0, Math.max(2, options.length)),
            building_ids: m2mIds(rec.building_ids),
            audience_group_ids: m2mIds(rec.audience_group_ids),
            buildingQuery: "",
            groupQuery: "",
        };
    }

    ratePct(rec) {
        return Math.round((rec.response_rate || 0) * 100);
    }

    categoryLabel(key) {
        return labelOf(POLL_CATEGORIES, key);
    }

    addOption() {
        this.state.form.options = [...(this.state.form.options || []), ""];
    }

    removeOption(index) {
        this.state.form.options = this.state.form.options.filter((_, i) => i !== index);
    }

    setOption(index, ev) {
        const options = [...this.state.form.options];
        options[index] = ev.target.value;
        this.state.form.options = options;
    }

    toggle(key) {
        this.state.form[key] = !this.state.form[key];
    }

    async save(publish) {
        return this.withBusy(publish ? "Publishing..." : "Saving...", async () => {
            const names = (this.state.form.options || []).map((n) => n.trim()).filter(Boolean);
            const errors = {};
            if (!(this.state.form.question || "").trim()) {
                errors.question = "A poll question is required.";
            }
            if (names.length < 2) {
                errors.options = "Add at least two options.";
            }
            this.validateAudience(errors);
            if (this.state.form.date_start && this.state.form.date_end) {
                const start = new Date(this.state.form.date_start);
                const end = new Date(this.state.form.date_end);
                if (end < start) {
                    errors.date_end = "End must be after the start.";
                }
            }
            if (!this.setErrors(errors)) {
                this.notification.add("Please fix the highlighted fields.", { type: "warning" });
                return;
            }
            const vals = {
                question: this.state.form.question,
                description: this.state.form.description,
                category: this.state.form.category,
                response_type: this.state.form.response_type,
                anonymous: Boolean(this.state.form.anonymous),
                one_per_unit: Boolean(this.state.form.one_per_unit),
                community_id: this.defaultCommunityId(),
                date_start: this.fromDatetimeLocal(this.state.form.date_start),
                date_end: this.fromDatetimeLocal(this.state.form.date_end),
                option_ids: names.map((name, index) => [0, 0, { name, sequence: (index + 1) * 10 }]),
                ...this.audienceVals(),
            };
            let id = this.state.resId;
            try {
                if (this.state.mode === "edit" && id) {
                    await this.orm.write("community.communication.poll", [id], {
                        ...vals,
                        option_ids: [[5, 0, 0], ...vals.option_ids],
                    });
                } else {
                    id = (await this.orm.create("community.communication.poll", [vals]))[0];
                }
                if (publish) {
                    await this.call("community.communication.poll", "action_open", [id]);
                    this.notification.add("Poll published", { type: "success" });
                } else {
                    this.notification.add("Draft saved", { type: "success" });
                }
                await this.setMode("detail", id);
            } catch (error) {
                if (!error?.data) {
                    await this.notifyError(error);
                }
            }
        });
    }

    selectOption(id) {
        const vote = this.state.extras.vote;
        if (!vote || vote.has_voted) {
            return;
        }
        if (vote.response_type === "single") {
            this.state.extras.selected = [id];
        } else if (this.state.extras.selected.includes(id)) {
            this.state.extras.selected = this.state.extras.selected.filter((x) => x !== id);
        } else {
            this.state.extras.selected = [...this.state.extras.selected, id];
        }
    }

    async submitVote() {
        if (!(this.state.extras.selected || []).length) {
            this.notification.add("Select at least one option.", { type: "warning" });
            return;
        }
        return this.withBusy("Submitting...", async () => {
            const payload = await this.call(
                "community.communication.poll",
                "action_vote",
                [this.state.resId, this.state.extras.selected]
            );
            this.state.extras.vote = payload;
            this.state.extras.confirmedAt = new Date().toISOString();
            this.state.mode = "confirm";
        });
    }

    async closePoll() {
        await this.call("community.communication.poll", "action_close", [this.state.resId]);
        this.setMode("results", this.state.resId);
    }

    exportResults() {
        const vote = this.state.extras.vote || {};
        const rows = [["Option", "Votes", "Percent"], ...(vote.options || []).map((o) => [o.name, o.vote_count, o.vote_percent])];
        this.exportRows("poll_results.csv", rows);
    }

    openPoll(rec) {
        if (this.state.isOfficer) {
            return this.setMode("results", rec.id);
        }
        return this.setMode(rec.state === "active" ? "vote" : "results", rec.id);
    }

    audienceText(rec) {
        return audienceLabel(rec);
    }

    previewBody() {
        return stripHtml(this.state.form.description || "").slice(0, 140);
    }

    selectedNames() {
        const vote = this.state.extras.vote || {};
        const selected = this.state.extras.selected || [];
        return (vote.options || []).filter((o) => selected.includes(o.id)).map((o) => o.name);
    }
}

registry.category("actions").add("community_communication.action_polls", CommunityPolls);
