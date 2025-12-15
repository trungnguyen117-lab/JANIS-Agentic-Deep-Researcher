import re
import requests
from typing import List, Tuple, Optional

try:
    import arxiv
    ARXIV_AVAILABLE = True
except ImportError:
    ARXIV_AVAILABLE = False
    print("[arXiv] Warning: arxiv library not installed. Install with: pip install arxiv")

from ..key_manager import KeyManager


def search_arxiv_with_llm(paragraph: str, llm, max_results: int = 5) -> Tuple[str, List[str]]:
    """
    Search arXiv for relevant papers using an LLM to generate search queries,
    then add citations to the paragraph.
    
    Args:
        paragraph: The paragraph text to add citations to
        llm: The LLM instance to use for generating search queries and adding citations
        max_results: Maximum number of papers to search for (default: 5)
    
    Returns:
        Tuple[str, List[str]]: (updated_paragraph_with_citations, list_of_arxiv_urls)
    """
    if not ARXIV_AVAILABLE:
        print("[arXiv] arxiv library not available, returning paragraph without citations")
        return paragraph, []
    
    try:
        # Use LLM to extract key terms and generate search query from paragraph
        search_prompt = f"""Given the following paragraph from a scientific paper, extract 2-3 key search terms or phrases that would help find relevant papers on arXiv.

Paragraph:
{paragraph}

Return only the search terms, separated by commas. For example: "federated learning, privacy, distributed systems"
"""
        
        # Generate search query
        search_response = llm.invoke(search_prompt)
        search_query = search_response.content.strip() if hasattr(search_response, 'content') else str(search_response).strip()
        
        # Clean up the query - take first few terms if it's too long
        search_terms = [term.strip() for term in search_query.split(',')[:3]]
        query = ' OR '.join(f'all:"{term}"' for term in search_terms if term)
        
        if not query:
            print(f"[arXiv] Could not generate search query, returning paragraph without citations")
            return paragraph, []
        
        print(f"[arXiv] Searching arXiv with query: {query}")
        
        # Search arXiv
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        # Get results
        results = list(search.results())
        
        if not results:
            print(f"[arXiv] No results found for query: {query}")
            return paragraph, []
        
        # Format citations for LLM
        citations_text = "\n".join([
            f"[{i+1}] {result.title} ({result.published.year}) - {result.summary[:200]}... "
            f"URL: https://arxiv.org/abs/{result.entry_id.split('/')[-1]}"
            for i, result in enumerate(results)
        ])
        
        # Use LLM to add citations to paragraph
        citation_prompt = f"""Given the following paragraph and a list of relevant papers, add citations in the format [1], [2], etc. where appropriate.

Paragraph:
{paragraph}

Relevant Papers:
{citations_text}

Return the paragraph with citations added in numerical format [1], [2], etc. Only add citations where they are clearly relevant. Do not alter the paragraph text otherwise.

Return only the paragraph with citations, nothing else.
"""
        
        citation_response = llm.invoke(citation_prompt)
        updated_paragraph = citation_response.content.strip() if hasattr(citation_response, 'content') else str(citation_response).strip()
        
        # Extract citation URLs
        arxiv_urls = [f"https://arxiv.org/abs/{result.entry_id.split('/')[-1]}" for result in results]
        
        print(f"[arXiv] Added {len(arxiv_urls)} citations to paragraph")
        return updated_paragraph, arxiv_urls
        
    except Exception as e:
        print(f"[arXiv] Error in search_arxiv_with_llm: {e}")
        import traceback
        print(f"[arXiv] Traceback: {traceback.format_exc()}")
        # Return original paragraph without citations on error
        return paragraph, []


def _execute_query(payload, keys: KeyManager):
    """
    Executes a query by sending a POST request to the Perplexity API.
    
    NOTE: This function uses blocking requests.post(). It's only called from
    perplexity() which is called from process_tex_file_with_references(), which
    is wrapped in run_in_executor() in add_citations_async(), so it's safe.

    Args:
        payload (dict[str, Any]): The payload to send in the API request.
        keys: KeyManager instance with API keys

    Returns:
        PerplexityChatCompletionResponse: Parsed response from the Perplexity API.
    
    Raises:
        ValueError: If API key is missing, request fails, or response is invalid
    """
    api_key = keys.PERPLEXITY
    if not api_key or api_key.strip() == "":
        raise ValueError("PERPLEXITY_API_KEY is not set. Please set it in your environment variables.")
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    try:
        response_obj = requests.post(
            "https://api.perplexity.ai/chat/completions", 
            headers=headers, 
            json=payload,
            timeout=60  # 60 second timeout
        )
        
        # Check status code
        response_obj.raise_for_status()
        
        # Check if response has content
        if not response_obj.text or not response_obj.text.strip():
            raise ValueError(f"Empty response from Perplexity API. Status code: {response_obj.status_code}")
        
        # Try to parse JSON
        try:
            response = response_obj.json()
        except requests.exceptions.JSONDecodeError as e:
            # Log the actual response for debugging
            print(f"[Perplexity] Failed to parse JSON response. Status: {response_obj.status_code}")
            print(f"[Perplexity] Response text (first 500 chars): {response_obj.text[:500]}")
            raise ValueError(
                f"Invalid JSON response from Perplexity API: {e}. "
                f"Status: {response_obj.status_code}, Response: {response_obj.text[:200]}"
            )

        return response
        
    except requests.exceptions.RequestException as e:
        print(f"[Perplexity] Request failed: {e}")
        raise ValueError(f"Perplexity API request failed: {e}")
    except Exception as e:
        print(f"[Perplexity] Unexpected error: {e}")
        raise


def perplexity(para, keys: KeyManager):
    perplexity_message = rf"""
You perform scientific literature search on the arXiv. 
    
Your goal is to populate the following text with references from the arXiv only:
    
<TEXT>
{para}
</TEXT>
    
You should return the text unaltered, with references added in numerical format, e.g. "[1]", "[2]", "[3]", etc.
    
    
For example, if the text is:
    
"Lorem ipsum dolor sit amet, nam ei dictas consequuntur delicatissimi, usu te epicuri epicurei, id vide nusquam conclusionemque ius. Vis alii nibh ex, per ex melius euripidis democritum. Vel eu suscipit reprehendunt, laoreet interpretaris vel at, sea habeo scripta referrentur ex. Sint ocurreret vix ad."
    
You should return the text with references added as in the example below:
    
"Lorem ipsum dolor sit amet, nam ei dictas consequuntur delicatissimi, usu te epicuri epicurei, id vide nusquam conclusionemque ius. Vis alii nibh ex, per ex melius euripidis democritum [1]. Vel eu suscipit reprehendunt, laoreet interpretaris vel at, sea habeo scripta referrentur ex [2][3]. Sint ocurreret vix ad [4]."
        
Only add references where you are sure that the reference is relevant to the paragraph and that it is necessary.
    
If a paragraph is very short, or if it is not clear what the paragraph is about, do not add any references and just return the paragraph without any references. If you don't easily find any references, just return the paragraph without any references.

Your answer should be the input text populated with references. You should not alter it in any way and not add any other information or explanations. Please follow these rules:

- Ignore tables, figures
- **Do not add citations inside tables or figures**
- Separate the different paragraphs, figures, and tables. Do not create a single long paragraph with all the text.

Your answear should not have the formating marks <TEXT> and </TEXT>, just the text.
    """
    payload = {
    "model": 'sonar-reasoning-pro',
    "temperature": 0,
    "messages": [{"role": "system", "content": "Be precise and concise. Follow the instructions."}, {"role": "user", "content": perplexity_message}],
    "search_domain_filter": ["arxiv.org"],
    }
    perplexity_response = _execute_query(payload, keys)
    content = perplexity_response["choices"][0]["message"]["content"]
    citations = perplexity_response["citations"]
    cleaned_response = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)

    def citation_repl(match):
        # Extract the citation number as a string and convert to an integer.
        number_str = match.group(1)
        index = int(number_str) - 1  # Adjust for 0-based indexing
        if 0 <= index < len(citations):
            return f'[[{number_str}]({citations[index]})]'
        # If the citation number is out of bounds, return it unchanged.
        return match.group(0)
    # Replace all instances of citations in the form [x] using the helper function.
    # markdown_response = re.sub(r'\[(\d+)\]', citation_repl, cleaned_response)
    #display(Markdown(markdown_response))
    return (cleaned_response, citations)



def process_tex_file_with_references(text, keys: KeyManager, nparagraphs=None, llm=None):
    """
    Processes a LaTeX file by inserting `\\citep{}` references and generating a corresponding .bib file.
    
    This pipeline:
      - Loads a .tex file as a list of lines.
      - Extracts paragraph-like lines using `_extract_paragraphs_from_tex_content()`, which returns a dict
        mapping 0-indexed line numbers to the corresponding line text.
      - For each identified paragraph, applies a perplexity function to generate updated text and citations.
      - Uses `_replace_references_with_cite()` to insert `\\citep{}` commands and update the BibTeX content.
      - Updates the corresponding line (using its original line index) in the list of lines.
      - Writes the modified .tex file and an updated bibliography file.
    
    Args:
        fname_tex (str): Path to the input .tex file.
        fname_bib (str): Path to the output .bib file.
        perplexity (callable): A function that processes a paragraph.
        nparagraphs (int, optional): Maximum number of paragraphs to process.
    """
    
    # Join lines to get the full text for paragraph extraction
    lines = text.splitlines()
    para_dict = _extract_paragraphs_from_tex_content(text)
    
    str_bib = ''  # initialize string for the .bib file content
    count = 0
    
    # Iterate through the extracted paragraphs in order of their line numbers
    for kpara in sorted(para_dict.keys()):
        # Optionally skip the first paragraph (or any others)
        if count == 0:
            count += 1
            continue
        
        para = para_dict[kpara]
        
        # Try to process the paragraph - use arXiv search instead of Perplexity
        new_para = None
        citations = []
        
        # Check if we should use Perplexity (if API key is available) or arXiv
        use_perplexity = keys.PERPLEXITY and keys.PERPLEXITY.strip() != ""
        
        if use_perplexity:
            # Try Perplexity first if API key is available, with simple retry
            for attempt in range(2):
                try:
                    new_para, citations = perplexity(para, keys)
                    if new_para is not None:
                        break  # exit the retry loop if successful
                except (ValueError, requests.exceptions.RequestException, KeyError, IndexError) as e:
                    print(f"[Perplexity] Error processing paragraph (attempt {attempt + 1}/2): {e}")
                    if attempt == 1:
                        # Fall back to arXiv on final attempt
                        print(f"[Perplexity] Falling back to arXiv search")
                        use_perplexity = False
                        break
                    # Wait a bit before retrying
                    import time
                    time.sleep(1)
                except Exception as e:
                    print(f"[Perplexity] Unexpected error, falling back to arXiv: {e}")
                    use_perplexity = False
                    break
        
        if not use_perplexity:
            # Use arXiv search (free, no API key needed)
            if llm is None:
                print(f"[arXiv] LLM not provided, skipping citation addition for this paragraph")
                new_para = para
                citations = []
            else:
                try:
                    new_para, citations = search_arxiv_with_llm(para, llm, max_results=5)
                    print(f"[arXiv] Found {len(citations)} relevant papers and added citations to paragraph")
                except Exception as e:
                    print(f"[arXiv] Error searching arXiv: {e}")
                    import traceback
                    print(f"[arXiv] Traceback: {traceback.format_exc()}")
                    # Use original paragraph without citations on error
                    new_para = para
                    citations = []
        
        if new_para is None:
            # Fallback: use original paragraph without citations
            new_para = para
            citations = []
        
        # Replace citation markers in the paragraph and update the BibTeX content
        new_para, str_bib = _replace_references_with_cite(new_para, citations, str_bib)
        
        # Update the line in the list only if the line index is valid
        lines[kpara] = new_para
        
        count += 1
        if nparagraphs is not None and count >= nparagraphs:
            break

    # Reassemble the text and write the updated files
    new_text = ''.join(lines)

    return new_text, str_bib



def _extract_paragraphs_from_tex_content(tex_content: str) -> dict:
    """
    Returns a dictionary mapping 0-indexed line numbers to lines that are likely part of a paragraph.
    
    Args:
        tex_content (str): LaTeX source as a string.

    Returns:
        dict: {line_number: line_text} for lines considered paragraph content.
    """
    paragraph_lines = {}
    lines = tex_content.splitlines(keepends=True)

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith('%'):
            continue

        if re.match(r'\\(begin|end|section|subsection|label|caption|ref|title|author|documentclass|usepackage|newcommand|section|subsection|subsubsection|affiliation|keywords|bibliography|centering|includegraphics)', line):
            continue

        if re.search(r'\\(item|enumerate)', line):    # consider removing?
            continue

        if re.search(r'(figure|table|equation|align|tabular)', line):
            continue

        if re.match(r'^\$.*\$$', line) or re.match(r'^\\\[.*\\\]$', line):
            continue

        paragraph_lines[i] = raw_line   # append the raw_line

    return paragraph_lines

def _arxiv_url_to_bib(citations: List[str]) -> Tuple[List[str], List[str]]:
    """
    Given a list of arXiv URLs, returns BibTeX keys and entries.

    Args:
        citations (List[str]): List of arXiv URLs (abs, pdf, or html variants allowed).

    Returns:
        Tuple[List[str], List[str]]:
            - A list of BibTeX keys (as strings).
            - A list of full BibTeX entries (as strings) suitable for inclusion in a .bib file.
    """
    bib_keys = []
    bib_strs = []

    for url in citations:

        try:
            # Convert URL to bibtex url (e.g., from /abs/ or /html/ to /bibtex/)
            bib_url = re.sub(r'\b(abs|html|pdf)\b', 'bibtex', url)
            # NOTE: This is a blocking call, but safe because called from thread executor
            response = requests.get(bib_url, timeout=10)

            # If fetching fails, try the fallback using the arXiv ID
            if response.status_code != 200:
                # Extract arXiv id from the URL (matches patterns like 2010.07487)
                match_id = re.search(r'(\d{4}\.\d+)', url)
                if match_id:
                    arxiv_id = match_id.group(1)
                    fallback_url = f"https://arxiv.org/bibtex/{arxiv_id}"
                    # NOTE: This is a blocking call, but safe because called from thread executor
                    response = requests.get(fallback_url, timeout=10)
                    if response.status_code != 200:
                        # Fallback failed; mark this citation as failed.
                        bib_keys.append(None)
                        continue
                else:
                    # Could not extract arXiv id; mark as failed.
                    bib_keys.append(None)
                    continue

            bib_str = response.text.strip()

            # Extract BibTeX key using regex
            match = re.match(r'@[\w]+\{([^,]+),', bib_str)
            if not match:
                # Could not extract key; mark as failed.
                bib_keys.append(None)
                continue

            bib_key = match.group(1)
            bib_keys.append(bib_key)
            bib_strs.append(bib_str)

        except Exception:
            bib_keys.append(None)
            continue

    return bib_keys, bib_strs

def _replace_grouped_citations(content: str, bib_keys: List[str]) -> str:
    """
    Replaces runs like [1][2][3] with a single sorted `\\citep{key1,key2,key3}`, sorted by year.
    Works for single refs like [1] too.

    Args:
        content (str): The paragraph containing [N] citation markers (1-indexed).
        bib_keys (List[str]): List of BibTeX keys corresponding to citations (0-indexed).

    Returns:
        str: Updated content with grouped citations merged and sorted by year.
    """

    def extract_year(key: str) -> int:
        """Extracts a 4-digit year from a BibTeX key (or returns a large number if missing)."""
        match = re.search(r'\d{4}', key)
        return int(match.group()) if match else float('inf')

    def replacer(match):
        # numbers = re.findall(r'\[(\d+)\]', match.group())  # ['1', '2', '3']
        # keys = [bib_keys[int(n) - 1] for n in numbers]     # adjust for 1-indexed
        # sorted_keys = sorted(keys, key=extract_year)
        # return f" \\citep{{{','.join(sorted_keys)}}}"
        numbers = re.findall(r'\[(\d+)\]', match.group())  # e.g. ['1', '2', '3']
        # Only include keys that were successfully fetched.
        keys = [bib_keys[int(n) - 1] for n in numbers if bib_keys[int(n) - 1] is not None]
        if not keys:
            return ""  # Remove citation markers if no valid keys exist.
        sorted_keys = sorted(keys, key=extract_year)
        return f" \\citep{{{','.join(sorted_keys)}}}"


    # Match sequences like [1][2][3]
    pattern = r'(?:\[\d+\])+'
    return re.sub(pattern, replacer, content)

def _replace_references_with_cite(content: str, citations: List[str], bibtex_file_str: str) -> Tuple[str, str]:
    """
    Replaces numeric reference markers like [1] in the content with LaTeX-style `\\citep{...}`,
    and appends corresponding BibTeX entries to the bibtex string.

    Args:
        content (str): A paragraph of text containing references like [1], [2], etc. (1-indexed).
        citations (List[str]): A list of arXiv URLs corresponding to the reference numbers. (0-indexed).
        bibtex_file_str (str): A string representing the contents of a .bib file.

    Returns:
        Tuple[str, str]:
            - The updated content with [N] replaced by `\\citep{BibTeXKey}`.
            - The updated BibTeX string with new entries appended.
    """
    bib_keys, bib_strs = _arxiv_url_to_bib(citations)

    # Replace all references with \citep{bibkey}
    content = _replace_grouped_citations(content, bib_keys)

    # Append all BibTeX entries to the .bib string
    bibtex_file_str = bibtex_file_str.rstrip() + '\n\n' + '\n\n'.join(bib_strs)

    return content, bibtex_file_str
