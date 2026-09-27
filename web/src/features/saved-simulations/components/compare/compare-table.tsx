import { Fragment } from 'react'
import type { Cell, CompareSection } from './compare-rows'

function CellView({ cell }: { cell: Cell }) {
  return 'text' in cell ? (
    <span className="tabular-nums">{cell.text}</span>
  ) : (
    <span className="text-xs font-normal italic text-(--sim-muted-foreground)">{cell.missing}</span>
  )
}

/** As duas revisões lado a lado, seção por seção. Sem vencedor, sem cor de melhor ou pior. */
export function CompareTable({ sections }: { sections: CompareSection[] }) {
  return (
    <section className="sim-card">
      {/* min-w: as duas colunas de valor mais o rótulo não cabem numa tela de celular; a rolagem
          lateral fica neste contêiner, sem levar a página inteira junto. */}
      <div className="relative overflow-x-auto">
        <table className="sim-compare-table w-full min-w-200 border-collapse text-xs">
          <thead>
            <tr>
              <th>Campo</th>
              <th className="w-75">A</th>
              <th className="w-75">B</th>
            </tr>
          </thead>
          <tbody>
            {sections.map((section) => (
              <Fragment key={section.title}>
                <tr>
                  <th colSpan={3} scope="colgroup">
                    {section.title}
                  </th>
                </tr>
                {section.rows.map((row) => (
                  <tr key={row.label}>
                    <th scope="row">{row.label}</th>
                    <td>
                      <CellView cell={row.a} />
                    </td>
                    <td>
                      <CellView cell={row.b} />
                    </td>
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
