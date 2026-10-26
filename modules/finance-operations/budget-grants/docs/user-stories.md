# budget-grants: user stories

Roles come from `contracts/permissions.yaml`. Each story names the contract operation that serves it.

## Finance staff

| # | Story | Contract |
|---|---|---|
| F1 | As finance staff I keep the list of budget heads (salaries, equipment, consumables, travel). | `GET/POST /budget-heads`, `PUT /budget-heads/{id}` |
| F2 | As finance staff I prepare a budget for a financial year, for the institution or a department, with an allocation per head, and send it for approval. | `POST /budgets`, `PUT /budgets/{id}`, `POST /budgets/{id}/submit` |
| F3 | As finance staff I ask to move money between two lines of an approved budget, with a reason. | `POST /reappropriations` |
| F4 | As finance staff I record spending that doesn't come from procurement or payroll, never above what is available, and reverse an entry made in error. | `POST /expenditures`, `POST /expenditures/{id}/reverse` |
| F5 | As finance staff I see commitments and actual spend on any line. | `GET /expenditures`, `GET /budgets/{id}` |
| F6 | As finance staff I see allocated, committed and spent per head for a year, with grant totals. | `GET /reports/budget-vs-spend` (widget `budget-vs-spend`) |
| F7 | As finance staff I'm told when a line reaches 80% and 100% of its allocation. | event `budget-grants.line.threshold-reached` |

## Management

| # | Story | Contract |
|---|---|---|
| M1 | As management I approve or return a budget someone else prepared. | `POST /budgets/{id}/decision` |
| M2 | As management I approve or reject a reappropriation someone else requested. | `POST /reappropriations/{id}/decision` |
| M3 | As management I certify a utilisation certificate someone else prepared. | `POST /utilisation-certificates/{id}/decision` |

## Research office

| # | Story | Contract |
|---|---|---|
| R1 | As the research office I record a sanctioned grant with its investigators and lines per head. | `POST /grants`, `PUT /grants/{id}` |
| R2 | As the research office I record each instalment the funder sends. | `POST /grants/{id}/funds-received` |
| R3 | As the research office I draft a utilisation certificate for a period from the records, and record when it was sent. | `POST /grants/{id}/utilisation-certificates`, `POST /utilisation-certificates/{id}/mark-submitted` |
| R4 | As the research office I'm reminded 30 and 7 days before a certificate is due. | event `budget-grants.utilisation-certificate.due` |
| R5 | As the research office I close a grant and record whether the unspent balance is returned or carried over. | `POST /grants/{id}/close` |
| R6 | As the research office I see budget against spend and grant totals. | `GET /reports/budget-vs-spend` (widget `budget-vs-spend`) |

## Investigators (faculty, research supervisors, research scholars)

| # | Story | Contract |
|---|---|---|
| I1 | As an investigator I see my grants with sanctioned amount, spent, balance and the next certificate due. | `GET /me/grants` (widget `my-grants`) |
| I2 | As an investigator I open one of my grants and its certificates. | `GET /grants/{id}`, `GET /grants/{id}/utilisation-certificates` |

## Other modules

| # | Story | Contract |
|---|---|---|
| X1 | procurement lists open budget and grant lines for an indent form, and checks that an amount is available before approving. | `GET /lines`, `GET /availability` |
| X2 | An issued purchase order becomes a commitment on its line; a cancelled one releases it; a paid vendor invoice turns the commitment into actual spend. | consumes `procurement.purchase-order.issued`, `.cancelled`, `procurement.vendor-invoice.paid` |
| X3 | A paid payroll run is charged to the salary head of the institution-wide budget. | consumes `hr-payroll.payroll-run.paid` |
