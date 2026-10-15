import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CcKpiHeader extends Component {
    static template = "community_communication.KpiHeader";
    static props = { list: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ cards: [] });
        onWillStart(async () => {
            const model = this.props.list?.resModel;
            if (!model) {
                return;
            }
            this.state.cards = await this.orm.call(
                "community.communication.dashboard",
                "get_list_kpis",
                [model]
            );
        });
    }

    onCardClick(card) {
        if (card.action) {
            this.action.doAction(card.action);
            return;
        }
        if (!card.filter || !this.env.searchModel) {
            return;
        }
        const items = this.env.searchModel.getSearchItems((item) => item.name === card.filter);
        this.env.searchModel.query = [];
        for (const item of items) {
            this.env.searchModel.toggleSearchItem(item.id);
        }
    }
}
