# Memória Externa para IA ("Second Brain") — Pesquisa de Mercado e Plano Piloto

**Data:** agosto de 2026
**Escopo:** levantamento do estado da arte em memória persistente para IA (agentes e assistentes pessoais), análise crítica de prós e contras dos principais projetos, e proposta de um piloto que combina os melhores padrões da concorrência corrigindo suas fraquezas — com **segurança e soberania de dados como requisito de primeira classe, não como feature**.

> Nota de terminologia: o pedido original mencionava "esconde brain", interpretado aqui como **Second Brain** (segundo cérebro) — a categoria de ferramentas de conhecimento pessoal — somada à categoria adjacente e tecnicamente mais profunda de **memory layers para agentes de IA**. As duas estão convergindo e o piloto ataca a interseção.

---

## 1. Como o mercado se divide hoje

O espaço se organiza em três camadas que raramente conversam entre si. Entender essa separação é o ponto de partida do piloto, porque a oportunidade está exatamente na costura entre elas.

| Camada | O que é | Exemplos | Dono do dado |
|---|---|---|---|
| **A. Apps de conhecimento pessoal** | Captura e organização humana, com IA adicionada por cima | Obsidian, Notion, Tana, Capacities, Reflect, Heptabase, NotebookLM, Saner.AI, MyMind | Varia: Obsidian/Logseq = local; Notion/Tana/NotebookLM = nuvem do fornecedor |
| **B. Memory layers para agentes** | Infraestrutura: extrair fatos, indexar, recuperar, versionar no tempo | Mem0, Zep/Graphiti, Letta (MemGPT), LangMem, Cognee, Supermemory, OpenMemory, Basic Memory | Majoritariamente API em nuvem; alguns self-hosted |
| **C. Captura ambiente / passiva** | Grava tudo (tela, áudio) e indexa | Microsoft Recall, Rewind, Limitless | Local com enclave (Recall) ou nuvem do fornecedor |

A camada A tem boa experiência de uso e péssima memória de máquina. A camada B tem boa memória de máquina e péssima ergonomia humana e governança. A camada C tem a captura mais rica e o pior perfil de risco de privacidade já visto na categoria.

---

## 2. Análise concorrencial — prós e contras

### 2.1 Camada B — infraestrutura de memória

#### Mem0
- **Prós:** maior comunidade da categoria (~48k estrelas no GitHub, +100 mil desenvolvedores, Série A de US$ 24M); SDK simples e adoção rápida; memória em escopos hierárquicos (conversa → sessão → usuário → organização) com promoção de fatos entre camadas; economia real de contexto — abaixo de ~7k tokens por chamada de recuperação contra 25k+ de abordagens full-context, e p95 de latência muito menor.
- **Contras:** **credibilidade dos números é o calcanhar de Aquiles** — o material da própria empresa cita 91,6% no LoCoMo, enquanto comparações independentes reproduzem algo entre 58% e 66%; roteia por API em nuvem por padrão (o dado sai da sua infra); recursos de grafo ("Mem0g") ficam atrás do tier de US$ 249/mês; a extração de fatos é LLM-dependente e silenciosamente perde nuance.

#### Zep / Graphiti
- **Prós:** o melhor modelo temporal do mercado — grafo de conhecimento onde entidades são nós e fatos são arestas **com intervalos de validade**, então ele sabe que algo "era verdade até março" em vez de guardar duas afirmações contraditórias; 63,8% no LongMemEval; núcleo (Graphiti) é open source.
- **Contras:** peso operacional alto — self-hosting exige Graphiti + banco de grafo (Neo4j/FalkorDB/Kuzu) + infraestrutura de embedding e LLM, no mínimo três sistemas para provisionar e monitorar; curva de aprendizado íngreme (episódios, entidades, janelas de validade, supersessão, procedência, travessia de grafo); o self-hosted é deliberadamente mais pobre que o Zep Cloud; **pegada de memória reportada acima de 600 mil tokens por conversa** em teste de terceiros, contra ~1,7k do Mem0; relatos de que a recuperação logo após a ingestão falha e a resposta correta só aparece horas depois (indexação assíncrona não sinalizada).

#### Letta (linhagem MemGPT)
- **Prós:** melhor acurácia pública da categoria — 83,2% no LongMemEval; arquitetura inspirada em SO com memória em níveis (blocos editáveis em contexto + memória arquival), e o agente gerencia a própria janela de contexto; caminho natural para agentes auto-evolutivos.
- **Contras:** **erros de raciocínio do agente corrompem a memória** — se o modelo decide errado o que gravar, o erro vira permanente e se auto-reforça; exige adotar o runtime Letta inteiro (Postgres + processo servidor + estado por agente), o que é muito mais pesado do que embrulhar um cliente de memória; latência sobe porque cada turno pode disparar chamadas de ferramenta de gestão de memória.

#### LangMem
- **Prós:** integração nativa e sem atrito para quem já vive em LangGraph; boa ergonomia dentro do ecossistema.
- **Contras:** acoplamento forte ao stack LangChain — fora dele o valor cai muito; é SDK, não plataforma: governança, auditoria e ciclo de vida do dado ficam por sua conta.

#### Cognee
- **Prós:** o mais completo entre os open source graph-native pensados para deployment local e privado; roda **totalmente local** com SQLite + LanceDB + KuzuDB embutidos, sem dependência de nuvem; defaults de conformidade com GDPR razoáveis; desenvolvimento ativo.
- **Contras:** construção de grafo é mais lenta e cara que embedding puro, e a qualidade do grafo é refém da qualidade do LLM extrator; menos maduro operacionalmente que Mem0 em volume; ainda exige que você monte a camada de produto por cima.

#### Supermemory
- **Prós:** licença MIT; posicionamento de "camada de memória universal" que ingere bookmarks, documentos e notas — bom para o caso pessoal, não só agentes.
- **Contras:** o ponto forte (ingerir tudo) é também o ponto fraco de segurança: ingestão indiscriminada é a superfície de ataque mais larga possível; maturidade de governança baixa.

#### Basic Memory / Obsidian Memory MCP / OpenMemory
- **Prós:** **a melhor resposta ao lock-in que existe hoje** — a fonte da verdade são arquivos Markdown em disco, com wikilinks, legíveis por humanos e por qualquer ferramenta; expostos por MCP, funcionam com Claude, Cursor, Codex, ChatGPT e qualquer cliente compatível; OpenMemory é local-first e não envia nada para fora.
- **Contras:** recuperação bem mais fraca que grafos temporais ou stacks vetoriais maduros; sem modelo de confiança, sem procedência, sem versionamento temporal — tudo que o agente escrever entra como verdade; escala mal quando o volume passa de alguns milhares de notas; nenhuma criptografia em repouso por padrão (o arquivo Markdown é texto claro no disco).

#### Engram
- **Prós:** o único projeto que trata privacidade como arquitetura e não como política — AES-256-GCM em repouso, **chaves nunca saem do dispositivo**, recuperação por mnemônico BIP39 de 24 palavras, armazenamento local em SQLite (`~/.engram/`), busca por blind index HMAC-SHA256 sem expor termos em claro, sync opcional sempre criptografado no cliente, e interface MCP.
- **Contras:** derivação de chave por **PBKDF2-SHA256 com 600k iterações** é aceitável mas está uma geração atrás do estado da arte (Argon2id resiste muito melhor a ataque com GPU/ASIC); blind index HMAC resolve busca exata, não semântica — a busca vetorial "sobre todas as sessões" implica um índice que precisa ser protegido separadamente, e é aí que mora o risco; sem modelo de procedência/confiança contra envenenamento; projeto jovem, sem auditoria externa publicada.

### 2.2 Camada A — apps de conhecimento pessoal

- **Obsidian** — **Prós:** Markdown puro no seu dispositivo, zero lock-in, plugins, e a feature Bases (tabelas estruturadas sobre YAML front-matter) na 1.9.10 aproxima o vault de um banco de dados. **Contras:** a IA é sempre um plugin de terceiros que lê o vault inteiro e manda para uma API — o modelo local-first do app é anulado no momento em que se liga a IA.
- **Notion** — **Prós:** ecossistema imbatível (notas → tarefas → wiki sem ginástica de API); barato (grátis pessoal, US$ 8/mês Plus, US$ 15/usuário Business). **Contras:** todo o conhecimento vive no servidor do fornecedor, em texto claro do ponto de vista do operador; exportação existe mas perde relações; nenhuma garantia criptográfica contra acesso interno ou ordem judicial.
- **Tana** — **Prós:** modelo de nós com supertags é a estrutura de dados mais expressiva da categoria, ideal para quem pensa em esquemas. **Contras:** curva de aprendizado alta, dependência de nuvem, exportação pobre.
- **NotebookLM** — **Prós:** grounding estrito nas fontes enviadas reduz alucinação de forma mensurável; ótimo para pesquisa fechada. **Contras:** não é memória — é um contêiner por notebook, sem continuidade entre sessões nem acúmulo; dado na nuvem do Google.
- **Saner.AI, MyMind, Reflect, Capacities, Heptabase** — **Prós:** captura de baixa fricção e boa UX. **Contras:** todos SaaS fechados; a memória é um ativo do fornecedor, não seu; risco de descontinuidade do produto = perda do segundo cérebro.

### 2.3 Camada C — captura ambiente

- **Microsoft Recall** — **Prós:** depois da reação negativa, virou referência técnica de mitigação: opt-in explícito, snapshots cifrados, dados dentro de enclave VBS inacessível até para admin/kernel sem autenticação biométrica, e armazenamento local em vez de upload. **Contras:** captura indiscriminada continua sendo captura indiscriminada — pega dados de terceiros que nunca consentiram (mensagens de outra pessoa na sua tela), cria alvo concentrado para intimação judicial e para malware pós-comprometimento, e a confiança do público não voltou.
- **Rewind / Limitless** — **Prós:** captura contínua de tela e áudio produz o corpus pessoal mais rico possível. **Contras:** gravação de áudio ambiente esbarra em consentimento de terceiros (no Brasil, LGPD art. 7º e 11 tornam isso especialmente delicado quando há dado sensível de terceiro); processamento em nuvem no modelo padrão.

---

## 3. O que a concorrência acertou (padrões a adotar)

1. **Markdown/arquivo simples como fonte da verdade** (Basic Memory, Obsidian) — elimina lock-in e torna o dado auditável a olho nu.
2. **Grafo temporal com intervalos de validade** (Zep/Graphiti) — a única forma correta de lidar com fatos que mudam.
3. **Escopos hierárquicos com promoção de fatos** (Mem0) — separa ruído de sessão de conhecimento durável.
4. **Orçamento explícito de contexto e recuperação enxuta** (Mem0) — memória que não cabe no contexto é inútil; <7k tokens por recall é a barra.
5. **Memória em níveis com blocos editáveis** (Letta) — o que o agente precisa sempre ver fica em contexto; o resto é arquival.
6. **Chaves que nunca saem do dispositivo + recuperação por mnemônico** (Engram) — a única postura de privacidade que sobrevive a um comprometimento do servidor.
7. **Enclave de hardware e opt-in explícito** (Recall pós-correção) — isolamento a nível de plataforma vale mais que promessa contratual.
8. **MCP como interface** (Basic Memory, Engram) — funciona com qualquer cliente e evita amarrar o usuário ao runtime.
9. **Grounding estrito nas fontes** (NotebookLM) — reduz alucinação e dá rastreabilidade da resposta até o documento.

---

## 4. O que todos erram (fraquezas a corrigir)

**F1 — Confiança indiscriminada na escrita.** Praticamente nenhum sistema distingue "o usuário me disse isto" de "li isto numa página web". Isso é fatal: pesquisa mostra que um atacante consegue envenenar memória de longo prazo por consultas normais, **sem privilégio nenhum, com >95% de sucesso de injeção e ~70% de sucesso de ataque**, e as defesas atuais contra prompt injection não cobrem memory poisoning. Injeção indireta consegue contaminar o resumo de sessão, persistir entre sessões e ser incorporada aos prompts de orquestração. A diferença estrutural é brutal: sem memória, a injeção morre com a sessão; com memória, ela fica no banco esperando ser recuperada, dando controle indefinido ao adversário **sem que ele precise manter acesso**. A corrupção se acumula devagar e se mistura à memória legítima, o que torna a detecção muito difícil.

**F2 — Deleção que não deleta.** As diretrizes EDPB 05/2019 exigem que a exclusão seja *verificável e irreversível*; suprimir o registro dos resultados de busca não basta. Mas não há mapeamento limpo entre o dado do usuário e quais vetores ele influenciou, e trabalho recente ("Ghost Vectors") mostra que **embeddings marcados como soft-deleted permanecem reconstrutíveis em índices HNSW**. Ou seja: quase todo produto da categoria hoje mente, sem querer, sobre o direito ao esquecimento.

**F3 — O índice vetorial é um vazamento de dados.** Se o dado-fonte está sob LGPD/GDPR, os embeddings também estão. Ataques de inversão reconstroem texto original a partir de vetores — nomes, diagnósticos médicos — com 60–80% de acurácia em embeddings de nível de sentença, e redução de dimensionalidade não resolve. Um vector store com leitura exposta é exposição de dado sensível, não "só números".

**F4 — Teatro de benchmark.** Cada fornecedor publica no benchmark em que ganha, o que torna comparação direta quase impossível e permite que todos aleguem liderança ao mesmo tempo. Os benchmarks medem acurácia de recuperação e **não dizem nada sobre latência, custo por token ou comportamento com contexto bagunçado** — que é o caso normal. Ninguém publica custo de produção por 1.000 recalls. E ninguém, absolutamente ninguém, publica **taxa de sucesso de ataque (ASR)**.

**F5 — Peso operacional desproporcional.** Três a cinco sistemas para rodar memória (Zep) ou um runtime inteiro (Letta) é caro demais para o valor entregue no caso pessoal e para times pequenos.

**F6 — Lock-in silencioso.** Mesmo os open source roteiam por API em nuvem por padrão, e o dado extraído (os *fatos*, não as notas) raramente é exportável em formato útil.

**F7 — Ausência de governança da escrita.** Falta procedência obrigatória por escrita, separação de tenancy, janelas de esquecimento deliberado, auditabilidade e avaliação contínua — exatamente o que o OWASP Top 10 para Aplicações Agênticas (2026) passou a cobrar como baseline.

**F8 — Nada de esquecimento por design.** Memória só cresce. Sem TTL, decaimento ou revisão, o sistema apodrece: contradições acumulam e o custo de recuperação sobe.

---

## 5. Projeto piloto — **ARCA** (Arquivo de Contexto Auditável)

### 5.1 Tese

> Uma memória externa para IA só é útil na medida em que é confiável, e só é confiável se **(a)** o usuário for criptograficamente dono dela, **(b)** cada fato carregar de onde veio, e **(c)** o esquecimento for verificável.
> Todo o resto — grafo, embeddings, escopos — é engenharia conhecida. A vantagem defensável do ARCA é ser o primeiro a tratar a memória como **superfície de ataque e ativo regulado**, e a publicar a métrica que ninguém publica: taxa de sucesso de envenenamento.

### 5.2 Princípios inegociáveis

1. **Local-first, cloud-optional.** Funciona 100% offline. Sync é opt-in e sempre cifrado no cliente.
2. **Zero-knowledge do operador.** Se o servidor de sync for totalmente comprometido, o atacante obtém ciphertext e metadados mínimos. Sem exceção para "features".
3. **Fonte da verdade legível por humanos.** Markdown + front-matter YAML, versionado em Git. Índices são derivados e descartáveis.
4. **Nenhuma escrita é confiável até ser classificada.** Procedência é campo obrigatório; conteúdo não confiável nunca vira instrução.
5. **Esquecimento é operação de primeira classe** com prova de execução.
6. **Sem lock-in.** Interface MCP; exportação completa é um `git clone` do vault.

### 5.3 Arquitetura

```
┌──────────────────────────────────────────────────────────────────┐
│  CLIENTES (Claude Code/Desktop, Cursor, ChatGPT, CLI, mobile)    │
│                      via  MCP  (stdio / local socket)            │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│  ARCA CORE  (processo local, Rust ou Python+Pydantic)            │
│                                                                  │
│  ┌───────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ WRITE GATEWAY │  │ RETRIEVAL ENGINE │  │ FORGET ENGINE    │   │
│  │ classificação │  │ híbrido + trust- │  │ TTL, decaimento, │   │
│  │ procedência,  │  │ aware reranking, │  │ deleção com prova│   │
│  │ PII, quaren-  │  │ orçamento de     │  │ e rebuild        │   │
│  │ tena          │  │ tokens           │  │                  │   │
│  └───────┬───────┘  └────────┬─────────┘  └────────┬─────────┘   │
│          │                   │                     │             │
│  ┌───────▼───────────────────▼─────────────────────▼─────────┐   │
│  │  CRYPTO LAYER — envelope AES-256-GCM, DEK por registro,   │   │
│  │  KEK via Argon2id, chaves em Secure Enclave/TPM           │   │
│  └───────┬───────────────────┬─────────────────────┬─────────┘   │
│          │                   │                     │             │
│  ┌───────▼──────┐  ┌─────────▼────────┐  ┌─────────▼─────────┐   │
│  │ VAULT        │  │ ÍNDICE VETORIAL  │  │ GRAFO TEMPORAL    │   │
│  │ Markdown+Git │  │ LanceDB cifrado  │  │ KuzuDB (embedded) │   │
│  │ FONTE DA     │  │ (DERIVADO)       │  │ (DERIVADO)        │   │
│  │ VERDADE      │  │                  │  │ fatos com         │   │
│  │              │  │                  │  │ valid_from/to     │   │
│  └──────────────┘  └──────────────────┘  └───────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ AUDIT LOG append-only, hash-chained + HMAC por entrada     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ EGRESS GUARD — decide o que pode sair para LLM remoto      │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                │ (opcional, opt-in)
┌───────────────────────────────▼──────────────────────────────────┐
│  SYNC RELAY — armazena apenas blobs cifrados. Zero-knowledge.    │
└──────────────────────────────────────────────────────────────────┘
```

**Decisões de arquitetura e por que elas corrigem fraquezas específicas:**

| Decisão | Corrige |
|---|---|
| Markdown+Git como fonte da verdade, índices 100% reconstrutíveis | F2 (deleção real = apaga na fonte + rebuild do shard, nunca soft-delete → mata o problema de *Ghost Vectors*), F6 (lock-in) |
| Embeddings gerados por **modelo local** (ex.: EmbeddingGemma/GTE em ONNX) | F3 — o texto nunca vai para uma API de embedding de terceiro |
| Índice vetorial dentro do envelope cifrado; blind index HMAC apenas para lookup exato | F3 — inversão de embedding exige primeiro quebrar AES-256 |
| Argon2id (não PBKDF2) para derivar a KEK, + Shamir 2-de-3 opcional para recuperação | Melhora explícita sobre o Engram |
| Procedência obrigatória + quarentena de escrita | F1, F7 |
| Grafo temporal com `valid_from`/`valid_to` sobre a mesma fonte Markdown | Copia Zep sem o peso de Neo4j (KuzuDB é embutido) — corrige F5 |
| Orçamento duro de tokens por recall com degradação previsível | F4 (mede o que importa) |
| TTL + decaimento + revisão trimestral assistida | F8 |

### 5.4 Modelo de dados

Cada memória é um arquivo Markdown com front-matter assinado:

```yaml
---
id: mem_01J8XK2...            # ULID
created_at: 2026-08-09T14:22:11Z
valid_from: 2026-08-09
valid_to: null                # null = vigente; datado = superseded
supersedes: [mem_01J7...]     # versionamento temporal explícito
scope: user                   # session | project | user | org
source_class: user_direct     # ↓ ver tabela de confiança
source_ref: "conversa://claude/2026-08-09#msg-42"
confidence: 0.95
sensitivity: normal           # public | normal | sensitive | secret
pii: [none]                   # detectado na ingestão
status: trusted               # candidate | trusted | quarantined | revoked
ttl: null                     # null = permanente; ISO8601 duration
entities: [projeto-arca, lgpd]
sig: "hmac-sha256:9f3a..."    # assinatura da entrada + elo da hash chain
---

Fato ou nota em texto legível.
```

**Tabela de classes de confiança (o núcleo da defesa contra F1):**

| `source_class` | Origem | Entra como | Pode virar instrução? | Peso no reranking |
|---|---|---|---|---|
| `user_direct` | Usuário digitou/confirmou | `trusted` | Sim | 1.00 |
| `user_document` | Arquivo que o usuário forneceu | `trusted` | Não — só citação | 0.85 |
| `agent_inference` | Conclusão do modelo | `candidate` | Não | 0.60 (após promoção) |
| `tool_output` | Saída de ferramenta/API | `candidate` | **Nunca** | 0.50 |
| `web_content` | Página, e-mail, PR, issue | `quarantined` | **Nunca** | 0.30 |
| `third_party_agent` | Outro agente | `quarantined` | **Nunca** | 0.20 |

Regra dura: **conteúdo abaixo de `user_direct` é entregue ao modelo dentro de um envelope `<dado_não_confiável origem="...">`, nunca no system prompt, e nunca é promovido a `trusted` sem confirmação humana explícita.**

### 5.5 Modelo de ameaças e controles

| # | Ameaça | Controle no ARCA |
|---|---|---|
| T1 | **Memory poisoning** por injeção indireta (>95% de sucesso de injeção na literatura) | Quarentena por classe de origem; screening de pré-ingestão (padrões imperativos, payloads codificados, anomalias de tamanho); nenhuma escrita de classe não confiável vira instrução; reranking ponderado por confiança |
| T2 | **Envenenamento lento e cumulativo** (difícil de detectar) | Monitoramento comportamental: alerta em taxa anômala de escrita, mudança brusca de tópico, contradição com memória `trusted` existente; revisão humana em lote semanal das promoções |
| T3 | **Exfiltração via memória** (a memória vira canal de saída) | Egress Guard: memória `sensitive`/`secret` exige confirmação humana antes de ir a LLM remoto; segredos são tokenizados e **nunca** embeddados; roteamento para modelo local quando `sensitivity >= sensitive` |
| T4 | **Inversão de embedding** (60–80% de reconstrução) | Embedding local + índice dentro do envelope cifrado + sem endpoint de leitura em rede |
| T5 | **Ghost vectors / deleção falsa** | Deleção = remover da fonte + **rebuild** do shard de índice + registro de prova (hash do índice antes/depois) no audit log |
| T6 | **Comprometimento do relay de sync** | Zero-knowledge: só ciphertext; metadados minimizados; sem chaves no servidor |
| T7 | **Adulteração do audit log** | Log append-only com hash chain e HMAC; âncora diária do hash raiz |
| T8 | **Perda de chave** | Recuperação por mnemônico BIP39 + Shamir 2-de-3 opcional (guardião/cofre físico) |
| T9 | **Captura de dado de terceiro sem consentimento** | **Sem captura ambiente na v1** — decisão de produto deliberada, ao contrário de Recall/Rewind. Ingestão é sempre um ato explícito |
| T10 | Erro do próprio agente corrompendo memória (falha do Letta) | Escrita do agente entra como `candidate` com TTL padrão de 30 dias; sem promoção, expira sozinha |

### 5.6 Privacidade e conformidade (LGPD / GDPR / EU AI Act)

- **Base legal e minimização (LGPD art. 6º, II e III):** ingestão explícita, nunca passiva; `sensitivity` e detecção de PII na entrada.
- **Direito à eliminação (LGPD art. 18, VI; GDPR art. 17):** o Forget Engine produz um recibo assinado — `{ids removidos, hash do índice antes, hash depois, timestamp}` — atendendo à exigência EDPB de exclusão *verificável e irreversível*.
- **Portabilidade (LGPD art. 18, V):** `git clone` do vault. Sem processo de exportação, sem formato proprietário.
- **Dado sensível de terceiro (LGPD art. 11):** política de não-captura ambiente na v1 + detector que sinaliza menções a terceiros identificáveis para revisão.
- **Registro de operações (LGPD art. 37; NIST AI RMF função Govern; EU AI Act para alto risco):** o audit log é o próprio registro, com IDs rastreáveis, versionamento, procedência da entrada e retenção configurável.
- **Relatório de impacto (RIPD):** entregável da Fase 4 do piloto.

### 5.7 Avaliação — a barra que o mercado não cumpre

Três suítes, resultados publicados **em conjunto e sempre juntos** (contra F4):

1. **Acurácia:** LongMemEval (500 questões) + LoCoMo (1.540 questões), com harness reproduzível público. Meta v1: ≥70% LongMemEval (entre Zep 63,8% e Letta 83,2%).
2. **Economia:** tokens medianos e p95 por recall (meta: **<5k**, abaixo dos ~7k do Mem0), latência p95 (meta: **<800ms local**), e **custo por 1.000 recalls** — número que nenhum concorrente publica.
3. **Segurança (a suíte diferencial):** `ARCA-Poison`, banco de 200 cenários adversariais cobrindo os quatro canais de escrita descritos na literatura — injeção via conteúdo web, via saída de ferramenta, via resumo de sessão e via agente terceiro. Métrica principal: **ASR (Attack Success Rate)**. Meta v1: **<5%**, contra ~70% de baseline reportado em sistemas sem quarentena. Publicar a suíte como open source, incluindo os resultados dos concorrentes.

> Publicar ASR comparativo é a jogada de posicionamento do piloto: cria uma dimensão de competição em que os líderes atuais começam perdendo, e é honesta — a suíte é aberta e eles podem melhorar.

### 5.8 Cronograma — 12 semanas

| Fase | Semanas | Entregáveis | Critério de saída |
|---|---|---|---|
| **0 — Fundação** | 1–2 | Vault Markdown+Git; crypto layer (envelope AES-256-GCM, Argon2id, Secure Enclave/TPM); audit log com hash chain; servidor MCP mínimo (`remember`, `recall`, `forget`) | Escrever e ler memória cifrada a partir do Claude Code; chave nunca em disco em claro |
| **1 — Recuperação** | 3–5 | Embedding local (ONNX); LanceDB cifrado; busca híbrida BM25+vetorial; grafo temporal KuzuDB com `valid_from/valid_to`; orçamento de tokens | ≥60% LongMemEval; p95 <800ms; <5k tokens/recall |
| **2 — Governança da escrita** | 6–8 | Write Gateway completo (classificação, procedência, PII, quarentena); trust-aware reranking; Egress Guard; suíte `ARCA-Poison` v1 | **ASR <5%**; nenhuma escrita `web_content` alcança system prompt em 200 cenários |
| **3 — Esquecimento e prova** | 9–10 | Forget Engine com rebuild e recibo assinado; TTL e decaimento; revisão assistida; sync relay zero-knowledge | Auditoria interna confirma zero recuperabilidade pós-deleção (incl. teste de reconstrução em HNSW) |
| **4 — Piloto com usuários** | 11–12 | 15–25 usuários internos por 3 semanas; RIPD; benchmark comparativo publicado; pentest externo contratado | Métricas de sucesso abaixo atingidas |

### 5.9 Equipe e custo estimado do piloto

| Papel | Alocação | 12 semanas |
|---|---|---|
| Eng. de sistemas (Rust/Python, crypto) | 1,0 FTE | — |
| Eng. de ML/recuperação | 1,0 FTE | — |
| Eng. de segurança (meio período) | 0,5 FTE | — |
| Produto/design | 0,5 FTE | — |
| **Custos diretos** | | |
| Pentest externo + revisão de criptografia | | US$ 15–25k |
| Compute de benchmark (LLM juiz, execuções) | | US$ 2–4k |
| Infra do relay de sync (piloto) | | ~US$ 300/mês |

Sem infraestrutura pesada porque a arquitetura é embarcada — isso é intencional e é o que corrige F5.

### 5.10 Métricas de sucesso e critérios de encerramento

**Sucesso (todos precisam ser atingidos):**
- ASR na suíte `ARCA-Poison` **< 5%**
- LongMemEval **≥ 70%**
- p95 de recall **< 800ms** local; **< 5k tokens** por recall
- Deleção verificável: **0** reconstruções bem-sucedidas em auditoria pós-deleção
- ≥60% dos pilotos usando ≥4 dias/semana na semana 3
- Pentest externo sem achado crítico ou alto em aberto

**Encerrar o piloto se:**
- ASR não descer abaixo de 15% até a semana 10 → a tese de governança de escrita não se sustenta na prática
- Latência local p95 > 2s com hardware de consumo → inviável como camada sempre ativa
- Criptografia por registro inviabilizar recuperação semântica com qualidade → o trade-off privacidade×utilidade é pior do que o previsto e exige repensar o design
- Menos de 30% de retenção na semana 3 → o problema não dói o suficiente no formato proposto

### 5.11 Riscos principais

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Criptografia por registro degradar a busca vetorial | Média | Alto | Prototipar na semana 1; plano B: índice em volume cifrado (SQLCipher) em vez de por registro |
| Qualidade do embedding local abaixo do de API | Média | Médio | Avaliar 3 modelos na Fase 1; permitir opt-in explícito para embedding remoto de conteúdo `public` apenas |
| Classificação de procedência gerar fricção excessiva | Alta | Médio | Defaults agressivos + promoção em lote semanal em vez de por item |
| Concorrentes copiarem a suíte de segurança | Alta | Baixo | É o objetivo — a vantagem é ser o primeiro e dono da métrica |
| Extração de fatos por LLM continuar sendo o elo fraco (problema do Zep e do Cognee) | Alta | Médio | Manter o Markdown original sempre recuperável: se a extração errar, a fonte está lá |

---

## 6. Resumo executivo em cinco linhas

O mercado de memória para IA já resolveu recuperação (Mem0, Letta), tempo (Zep) e portabilidade (Basic Memory), e falhou coletivamente em três coisas: **não distingue de onde veio cada memória** (envenenamento com ~70% de sucesso), **não deleta de verdade** (embeddings soft-deleted continuam reconstrutíveis) e **transforma o índice vetorial num vazamento** (inversão reconstrói texto com 60–80% de acurácia). O ARCA copia o que funciona — Markdown como fonte da verdade, grafo temporal embarcado, escopos hierárquicos, chaves que nunca saem do dispositivo — e adiciona as três peças ausentes: **procedência obrigatória com quarentena, esquecimento com prova criptográfica, e embedding local dentro do envelope cifrado**. O piloto dura 12 semanas, custa cerca de 3 FTEs mais US$ 20–30k de custos diretos, e se valida ou se mata contra uma métrica que ninguém no mercado publica hoje: a taxa de sucesso de envenenamento da memória.

---

## Fontes

**Comparativos de memory layers**
- [AI Agent Memory 2026 — Comparing Mem0, Zep, Graphiti, Letta, LangMem (Medium)](https://medium.com/@wasowski.jarek/i-compared-5-ai-agent-memory-systems-across-6-dimensions-none-wins-6a658335ed0a)
- [Mem0 vs Zep vs Letta vs Cognee: Which to Use in 2026 (Particula)](https://particula.tech/blog/agent-memory-frameworks-tested-mem0-zep-letta-cognee-2026)
- [Mem0 vs Zep vs Letta: AI Agent Memory in 2026 (Datapace)](https://datapace.ai/blog/ai-agent-memory-tools-2026)
- [Best AI Agent Memory Frameworks in 2026 (RockB)](https://baeseokjae.github.io/posts/best-ai-agent-memory-frameworks-2026/)
- [AI Memory Solutions Compared: Q3 2026 (Mnemoverse)](https://mnemoverse.com/docs/library/ai-memory-solutions-2026-q3)
- [Mem0 vs Zep (Graphiti): Agent Memory Compared (Vectorize)](https://vectorize.io/articles/mem0-vs-zep)
- [Best SuperMemory Alternatives for Agent Memory in 2026 (Vectorize)](https://vectorize.io/articles/supermemory-alternatives)

**Benchmarks e custo**
- [Agent Memory Benchmarks 2026: The Real Numbers (memnode)](https://memnode.dev/articles/agent-memory-benchmarks-2026-real-numbers)
- [Mem0 Research: LoCoMo, LongMemEval & BEAM](https://mem0.ai/research)
- [AI Memory Benchmarks 2026 (Mem0)](https://mem0.ai/blog/ai-memory-benchmarks-in-2026)

**Open source e local-first**
- [Cognee — Open-Source AI Memory Platform (GitHub)](https://github.com/topoteretes/cognee)
- [Best Open-Source AI Memory Tools for LLMs 2026 (Cognee)](https://www.cognee.ai/blog/guides/best-open-source-ai-memory-tools-for-llm-agents-and-developers)
- [Engram — Privacy-first AI memory layer, E2EE, local-first (GitHub)](https://github.com/EvolvingLMMs-Lab/engram)
- [Basic Memory MCP Server](https://mcpservers.org/servers/basicmachines-co/basic-memory)
- [obsidian-memory-mcp (GitHub)](https://github.com/YuNaga224/obsidian-memory-mcp)
- [opencode-openmemory (GitHub)](https://github.com/happycastle114/opencode-openmemory)

**Second brain / PKM**
- [11 Best AI Second Brain Tools 2026 (Taskade)](https://www.taskade.com/blog/ai-second-brain-tools)
- [16 Best Second Brain Apps in 2026 (Buildin)](https://buildin.ai/blog/best-second-brain-apps-2026)
- [7 Best Second Brain Apps 2026: Cognitive-Load Tested (Atlas)](https://www.atlasworkspace.ai/blog/best-second-brain-apps)
- [AI Second Brain Software Comparison (Teknalyze)](https://www.teknalyze.com/software/ai-second-brain-software-tested-compared-and-explained/)

**Segurança de memória**
- [When AI Remembers Too Much — Indirect Prompt Injection Poisons Long-Term Memory (Unit 42)](https://unit42.paloaltonetworks.com/indirect-prompt-injection-poisons-ai-longterm-memory/)
- [From Untrusted Input to Trusted Memory: Memory Poisoning Attacks in LLM Agents (arXiv 2606.04329)](https://arxiv.org/html/2606.04329v1)
- [AI Memory / Context Poisoning (Microsoft Learn)](https://learn.microsoft.com/en-us/security/zero-trust/catalog-ai-attack-techniques/ai-memory-context-poisoning)
- [Agentic AI Threats: Memory Poisoning & Long-Horizon Goal Hijacks (Lakera)](https://www.lakera.ai/blog/agentic-ai-threats-p1)
- [Manipulating AI memory for profit: AI Recommendation Poisoning (Microsoft Security)](https://www.microsoft.com/en-us/security/blog/2026/02/10/ai-recommendation-poisoning/)
- [Persistent memory poisoning in AI agents (Christian Schneider)](https://christian-schneider.net/blog/persistent-memory-poisoning-in-ai-agents/)
- [How to Prevent AI Memory Poisoning: Defense in Depth (Vectorize)](https://vectorize.io/articles/how-to-prevent-ai-memory-poisoning)
- [OWASP Top 10 for Agentic Applications 2026 (Cycode)](https://cycode.com/blog/owasp-top-10-agentic-applications/)
- [Memory Governance Is Becoming the Control Plane for Agentic AI (HackerNoon)](https://hackernoon.com/memory-governance-is-becoming-the-control-plane-for-agentic-ai)

**Privacidade de embeddings e deleção**
- [Ghost Vectors: Soft-Deleted Embeddings Remain Reconstructible in HNSW (arXiv 2606.18497)](https://arxiv.org/pdf/2606.18497)
- [Vector Embedding Inversion: Reconstructing Sensitive Data (Aquilax)](https://aquilax.ai/blog/vector-embedding-inversion-attacks)
- [The Privacy Architecture of Embeddings (TianPan.co)](https://tianpan.co/blog/2026-04-19-privacy-architecture-embeddings-vector-store)
- [RAG Security Cheat Sheet (OWASP)](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)
- [How do vector DBs comply with GDPR? (Milvus)](https://milvus.io/ai-quick-reference/how-do-vector-dbs-comply-with-legal-data-privacy-regulations-eg-gdpr)

**Criptografia e captura ambiente**
- [Encrypted AI Agent Memory: Secure Personalization (ZetaChain)](https://www.zetachain.com/blog/encrypted-ai-agent-memory-personalization)
- [End-to-End Encrypted AI Inference with Post-Quantum Cryptography (Chutes)](https://chutes.ai/news/end-to-end-encrypted-ai-inference-with-post-quantum-cryptography)
- [Private AI API with end-to-end encryption (Privatemode)](https://www.privatemode.ai/inference-api)
- [Privacy and security risks surrounding Microsoft Recall (TechTarget)](https://www.techtarget.com/searchenterpriseai/feature/Privacy-and-security-risks-surrounding-Microsoft-Recall)
- [Privacy Anxiety Pushes Microsoft Recall Release Again (Dark Reading)](https://www.darkreading.com/application-security/privacy-anxiety-pushes-microsoft-recall-release-again)
- [Why Microsoft's New AI Feature Has Prompted Privacy Concerns (TIME)](https://time.com/6980911/microsoft-copilot-recall-ai-features-privacy-concerns/)

**Governança e auditoria**
- [AI Audit Trail: 7 Things to Log for Compliance in 2026 (Superblocks)](https://www.superblocks.com/blog/ai-audit-trail)
- [AI Governance and Audit Trails for Enterprise LLM Observability (Confident AI)](https://www.confident-ai.com/knowledge-base/guides/enterprise-ai-governance-audit-trails)
