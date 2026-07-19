import { useEffect, useState, useMemo } from 'react'
import { toast } from 'sonner'
import { graphApi, type GraphData, type GraphNode } from '@/api/graph'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import Graph from 'graphology'
import { SigmaContainer, useSigma } from '@react-sigma/core'
import { MiniMap } from '@react-sigma/minimap'
import forceAtlas2 from 'graphology-layout-forceatlas2'
import circular from 'graphology-layout/circular'
import force from 'graphology-layout-force'
import noverlap from 'graphology-layout-noverlap'
import random from 'graphology-layout/random'
import { Search, Loader2, X } from 'lucide-react'
import '@react-sigma/core/lib/style.css'

const LAYOUTS = [
  { value: 'forceatlas2', label: 'ForceAtlas2' },
  { value: 'circular', label: 'Circular' },
  { value: 'force', label: 'Force' },
  { value: 'circlepack', label: 'CirclePack' },
  { value: 'noverlap', label: 'Noverlap' },
  { value: 'random', label: 'Random' },
] as const

function applyLayout(graph: Graph, layout: string) {
  const nodes = graph.nodes()
  if (nodes.length === 0) return

  switch (layout) {
    case 'forceatlas2':
      forceAtlas2.assign(graph, { iterations: 50, settings: { scalingRatio: 10, gravity: 1 } })
      break
    case 'circular':
      circular.assign(graph, {})
      break
    case 'force':
      force.assign(graph, { maxIterations: 50 })
      break
    case 'noverlap':
      noverlap.assign(graph, { maxIterations: 50 })
      break
    case 'random':
      random.assign(graph, { scale: 100 })
      break
    default:
      circular.assign(graph, {})
  }
}

function GraphEvents({ onNodeClick }: { onNodeClick: (node: string) => void }) {
  const sigma = useSigma()
  useEffect(() => {
    const handler = ({ node }: { node: string }) => {
      onNodeClick(node)
    }
    sigma.on('clickNode', handler)
    return () => {
      sigma.off('clickNode', handler)
    }
  }, [sigma, onNodeClick])
  return null
}

export default function KnowledgeGraph() {
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<string[]>([])
  const [selectedLabel, setSelectedLabel] = useState<string>('')
  const [maxDepth, setMaxDepth] = useState(3)
  const [maxNodes, setMaxNodes] = useState(1000)
  const [layout, setLayout] = useState<string>('forceatlas2')
  const [loading, setLoading] = useState(false)
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  const graph = useMemo(() => new Graph(), [])

  const handleSearch = async () => {
    if (!search.trim()) return
    try {
      const results = await graphApi.searchLabels(search.trim())
      setSearchResults(results)
      if (results.length === 0) {
        toast.info('未找到匹配的标签')
      }
    } catch {
      // 拦截器已 toast
    }
  }

  const handleLoadGraph = async (label: string) => {
    if (!label) return
    setLoading(true)
    setSelectedNode(null)
    try {
      const data = await graphApi.getGraph({
        label,
        max_depth: maxDepth,
        max_nodes: maxNodes,
      })
      setGraphData(data)
      setSelectedLabel(label)

      // 构建 graphology 实例
      graph.clear()
      for (const node of data.nodes || []) {
        if (!graph.hasNode(node.id)) {
          graph.addNode(node.id, {
            label: node.label,
            x: Math.random(),
            y: Math.random(),
            size: Math.max(5, Math.min(20, (node.degree || 1) * 2)),
            color: '#6366f1',
          })
        }
      }
      for (const edge of data.edges || []) {
        const edgeId = edge.id || `${edge.source}-${edge.target}`
        if (!graph.hasEdge(edge.source, edge.target)) {
          graph.addEdge(edge.source, edge.target, {
            id: edgeId,
            label: edge.label || '',
            color: '#cbd5e1',
            size: 1,
          })
        }
      }
      applyLayout(graph, layout)
      toast.success(`已加载 ${data.nodes?.length || 0} 个节点，${data.edges?.length || 0} 条边`)
    } finally {
      setLoading(false)
    }
  }

  const handleLayoutChange = (newLayout: string) => {
    setLayout(newLayout)
    if (graphData) {
      applyLayout(graph, newLayout)
      // 触发重渲染
      setGraphData({ ...graphData })
    }
  }

  const handleNodeClick = (nodeId: string) => {
    const node = graphData?.nodes.find(n => n.id === nodeId)
    if (node) {
      setSelectedNode(node)
    }
  }

  const nodeAttributes = selectedNode
    ? graph.getNodeAttributes(selectedNode.id)
    : null

  return (
    <div className="flex h-full flex-col">
      {/* 工具栏 */}
      <div className="flex items-center gap-2 border-b p-3">
        <div className="flex flex-1 items-center gap-2">
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="搜索标签..."
            className="max-w-xs"
          />
          <Button size="sm" variant="outline" onClick={handleSearch}>
            <Search className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Label className="text-xs">深度:</Label>
          <Input
            type="number"
            value={maxDepth}
            onChange={e => setMaxDepth(Number(e.target.value) || 3)}
            className="w-16"
            min={1}
            max={5}
          />
          <Label className="text-xs">节点上限:</Label>
          <Input
            type="number"
            value={maxNodes}
            onChange={e => setMaxNodes(Number(e.target.value) || 1000)}
            className="w-24"
            min={1}
            max={5000}
          />
          <Label className="text-xs">布局:</Label>
          <Select value={layout} onValueChange={handleLayoutChange}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LAYOUTS.map(l => (
                <SelectItem key={l.value} value={l.value}>
                  {l.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* 搜索结果 */}
      {searchResults.length > 0 && (
        <div className="flex flex-wrap gap-2 border-b p-2">
          {searchResults.map(label => (
            <Badge
              key={label}
              variant={selectedLabel === label ? 'default' : 'outline'}
              className="cursor-pointer"
              onClick={() => handleLoadGraph(label)}
            >
              {label}
            </Badge>
          ))}
        </div>
      )}

      {/* 图渲染区 + 节点详情 */}
      <div className="flex flex-1 overflow-hidden">
        <div className="relative flex-1">
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          )}
          {!graphData && !loading && (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              搜索标签并选择一个以加载知识图谱
            </div>
          )}
          {graphData && (
            <SigmaContainer
              graph={graph}
              settings={{
                defaultEdgeColor: '#cbd5e1',
                labelDensity: 0.07,
                labelGridCellSize: 60,
                labelRenderedSizeThreshold: 12,
                renderEdgeLabels: true,
                minCameraRatio: 0.05,
                maxCameraRatio: 10,
              }}
              style={{ height: '100%', width: '100%' }}
            >
              <GraphEvents onNodeClick={handleNodeClick} />
              <MiniMap width="150px" height="150px" />
            </SigmaContainer>
          )}
        </div>

        {/* 节点详情面板 */}
        {selectedNode && (
          <div className="w-80 shrink-0 border-l p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-medium">节点详情</span>
              <Button variant="ghost" size="sm" onClick={() => setSelectedNode(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <ScrollArea className="h-[calc(100%-3rem)]">
              <div className="space-y-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Label:</span>{' '}
                  {selectedNode.label}
                </div>
                {selectedNode.type && (
                  <div>
                    <span className="text-muted-foreground">Type:</span>{' '}
                    {selectedNode.type}
                  </div>
                )}
                <div>
                  <span className="text-muted-foreground">Degree:</span>{' '}
                  {selectedNode.degree || nodeAttributes?.['size'] || '-'}
                </div>
                {selectedNode.properties &&
                  Object.keys(selectedNode.properties).length > 0 && (
                  <div>
                    <span className="text-muted-foreground">Properties:</span>
                    <pre className="mt-1 overflow-auto rounded bg-muted p-2 text-xs">
                      {JSON.stringify(selectedNode.properties, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>
    </div>
  )
}
