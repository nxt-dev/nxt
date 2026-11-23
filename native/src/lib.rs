//! Native twins of hot nxt functions.
//!
//! Each function here must give exactly what its Python twin gives, for every
//! input. nxt only uses them when this module loads, and falls back to the
//! Python code when it doesn't. See nxt/native.py.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};

mod comp;

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

/// Twin of comp_plan.Plan: composites as data and returns what to make.
/// See comp_plan.native_build for the arguments and the result. Raises
/// ValueError starting "fallback:" for a comp to do the old way.
#[pyfunction]
#[pyo3(signature = (keys, node_attrs, specs, tables, comp_real_path, layers, overload_order, make, strict=false))]
fn comp_plan(
    py: Python<'_>,
    keys: Vec<Py<PyAny>>,
    node_attrs: &Bound<'_, PyList>,
    specs: &Bound<'_, PyList>,
    tables: &Bound<'_, PyList>,
    comp_real_path: &Bound<'_, PyAny>,
    layers: &Bound<'_, PyDict>,
    overload_order: Vec<u8>,
    make: &Bound<'_, PyTuple>,
    strict: bool,
) -> PyResult<PyObject> {
    use std::collections::HashMap;
    let mut plan = comp::Plan::new(overload_order, strict);
    let real_path = plan.to_val(comp_real_path)?;
    let mut layer_map: HashMap<String, Option<comp::Val>> = HashMap::new();
    for (k, v) in layers.iter() {
        let key: String = k.extract()?;
        let val = if v.is_none() { None } else { Some(plan.to_val(&v)?) };
        layer_map.insert(key, val);
    }
    plan.set_comp_layer(real_path, layer_map);
    let read_dict = |plan: &mut comp::Plan, items: &Bound<'_, PyList>| -> PyResult<Vec<(u8, comp::Val)>> {
        let mut out = Vec::with_capacity(items.len());
        for item in items.iter() {
            let (k, v): (u8, Bound<'_, PyAny>) = item.extract()?;
            out.push((k, plan.to_val(&v)?));
        }
        Ok(out)
    };
    let node = read_dict(&mut plan, node_attrs)?;
    plan.add_node_class(node);
    for (i, spec) in specs.iter().enumerate() {
        let items = spec.downcast::<PyList>()?;
        let dict = read_dict(&mut plan, items)?;
        plan.add_spec_class(i, dict);
    }
    let mut parsed: Vec<Vec<(comp::SL, comp::Cid)>> = Vec::with_capacity(tables.len());
    for table in tables.iter() {
        let table = table.downcast::<PyList>()?;
        let mut rows = Vec::with_capacity(table.len());
        for row in table.iter() {
            let (ns, spec): (Bound<'_, PyAny>, usize) = row.extract()?;
            let ns = match plan.to_val(&ns)? {
                comp::Val::List(l) => l,
                _ => return Err(pyo3::exceptions::PyValueError::new_err(
                    "fallback: a namespace that is not a list of strings")),
            };
            rows.push((ns, spec + 1));
        }
        parsed.push(rows);
    }
    let timing = std::env::var("NXT_COMP_TIMING").map(|v| v == "1").unwrap_or(false);
    let run = |plan: &mut comp::Plan| -> Result<(usize, i64, usize, usize, usize), String> {
        let t = std::time::Instant::now();
        let node_count = plan.comp_pre_proxies(&parsed)?;
        let t1 = t.elapsed();
        let (proxy_count, loops) = plan.comp_proxies(node_count)?;
        let t2 = t.elapsed();
        let (root_count, total_count) = plan.post_proxy_comp()?;
        let t3 = t.elapsed();
        if timing {
            eprintln!("native comp: pre {:?} proxies {:?} post {:?}", t1, t2 - t1, t3 - t2);
            plan.print_timing();
        }
        Ok((node_count, proxy_count, loops, root_count, total_count))
    };
    let counts = match run(&mut plan) {
        Ok(c) => c,
        Err(why) => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!("fallback: {}", why)));
        }
    };
    let t = std::time::Instant::now();
    // (type, Node, spec classes, module name, SpecNode name, CompNode name,
    //  LayerReturnTypes Node, Path, NodeTable, NameDict)
    let args = comp::MakeArgs {
        keys,
        type_fn: make.get_item(0)?.unbind(),
        node: make.get_item(1)?.unbind(),
        specs: make.get_item(2)?.downcast::<PyList>()?.iter().map(|o| o.unbind()).collect(),
        module: make.get_item(3)?.unbind(),
        spec_name: make.get_item(4)?.unbind(),
        comp_name: make.get_item(5)?.unbind(),
        return_types: (6..10).map(|i| make.get_item(i).map(|o| o.unbind())).collect::<PyResult<Vec<_>>>()?,
    };
    let result = plan.make(py, &args)?;
    if timing {
        eprintln!("native comp: result {:?}", t.elapsed());
    }
    let counts = (counts.0, counts.1, counts.2, counts.3, counts.4).into_pyobject(py)?.into_any().unbind();
    Ok(pyo3::types::PyTuple::new(py, [result, counts])?.into_any().unbind())
}

#[pymodule]
fn _nxt_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("VERSION", 4)?;
    m.add_function(wrap_pyfunction!(standalone_tokens, m)?)?;
    m.add_function(wrap_pyfunction!(comp_plan, m)?)?;
    Ok(())
}
