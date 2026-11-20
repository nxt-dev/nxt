//! Native twins of hot nxt functions.
//!
//! Each function here must give exactly what its Python twin gives, for every
//! input. nxt only uses them when this module loads, and falls back to the
//! Python code when it doesn't. See nxt/native.py.

use pyo3::prelude::*;

const PREFIX: [char; 2] = ['$', '{'];
const SUFFIX: char = '}';

/// Twin of the scanning part of nxt.tokens.get_standalone_tokens.
///
/// Returns the tokens in `raw` that are not nested in another token, keeping
/// those that start with "${" followed by one of `prefixes`. Malformed token
/// syntax (more starts than ends) gives an empty list, as in Python.
#[pyfunction]
fn standalone_tokens(raw: &str, prefixes: Vec<String>) -> Vec<String> {
    if !raw.contains("${") {
        return Vec::new();
    }
    // Python indexes by character, so work on characters, not bytes.
    let chars: Vec<char> = raw.chars().collect();
    let n = chars.len();
    let mut bounds: Vec<(usize, usize)> = Vec::new();
    let mut starts: usize = 0;
    let mut ends: usize = 0;
    let mut outer_start: usize = 0;
    for i in 0..n {
        let c = chars[i];
        if i + 1 < n && c == PREFIX[0] && chars[i + 1] == PREFIX[1] {
            if starts == 0 {
                outer_start = i;
            }
            starts += 1;
        } else if starts > 0 && c == SUFFIX {
            ends += 1;
        }
        if starts > 0 && starts == ends {
            bounds.push((outer_start, i + 1));
            starts = 0;
            ends = 0;
        }
    }
    if starts != ends {
        return Vec::new();
    }
    let mut results = Vec::with_capacity(bounds.len());
    for (start, end) in bounds {
        let token: String = chars[start..end].iter().collect();
        let keep = prefixes
            .iter()
            .any(|p| token.starts_with(&format!("${{{}", p)));
        if keep {
            results.push(token);
        }
    }
    results
}

#[pymodule]
fn _nxt_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("VERSION", 1)?;
    m.add_function(wrap_pyfunction!(standalone_tokens, m)?)?;
    Ok(())
}
