export type VisualPath = { segmentIds: number[]; proposalIds: number[] };

export function reconstructVisualPaths(
  proposals: Array<{segment_a: number; segment_b: number}>,
  reviews: Record<number, "accepted" | "rejected">,
): VisualPath[] {
  const adjacency = new Map<number, Set<number>>();
  const accepted = proposals.map((proposal, index) => ({...proposal, index}))
    .filter(proposal => reviews[proposal.index] === "accepted");
  for (const proposal of accepted) {
    for (const id of [proposal.segment_a, proposal.segment_b]) {
      if (!adjacency.has(id)) adjacency.set(id, new Set());
    }
    adjacency.get(proposal.segment_a)!.add(proposal.segment_b);
    adjacency.get(proposal.segment_b)!.add(proposal.segment_a);
  }
  const visited = new Set<number>();
  const paths: VisualPath[] = [];
  for (const start of adjacency.keys()) {
    if (visited.has(start)) continue;
    const queue = [start];
    visited.add(start);
    const members: number[] = [];
    while (queue.length) {
      const current = queue.shift()!;
      members.push(current);
      for (const neighbor of adjacency.get(current)!) {
        if (!visited.has(neighbor)) { visited.add(neighbor); queue.push(neighbor); }
      }
    }
    const set = new Set(members);
    paths.push({
      segmentIds: members.sort((a, b) => a - b),
      proposalIds: accepted.filter(p => set.has(p.segment_a) && set.has(p.segment_b)).map(p => p.index),
    });
  }
  return paths.sort((a, b) => b.segmentIds.length - a.segmentIds.length);
}
