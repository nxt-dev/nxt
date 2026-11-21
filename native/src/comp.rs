//! Native twin of nxt/comp_plan.py: compositing worked out as data.
//!
//! Each function mirrors the Plan method of the same name, which mirrors the
//! Stage method it is named after. Read comp_plan.py for why each step is
//! the way it is; this file only has to match it. Anything comp_plan raises
//! Fallback for is an Err here, and the caller composites the old way.
//!
//! It matches down to which values are the same Python object, since nxt
//! tests some with `is` (a path against nxt_path.WORLD, a child name against
//! a child order). A string here is an Rc<str> and a list an Rc'd Vec, and
//! each Rc is one Python object: the object it was read from, or one made
//! for it at the end. So each step makes a new string or list where Python
//! makes a new object, and passes the same one on where Python does,
//! including where CPython hands back the object it was given (a replace
//! that replaces nothing, a split that finds no separator). The empty string
//! and one character strings are one object each in CPython, whatever made
//! them, and so they are here.

use std::cell::{Ref, RefCell};
use std::collections::{HashMap, HashSet};
use std::rc::Rc;

use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyList, PyString, PyTuple};

pub type Cid = usize;
pub const OBJECT: Cid = usize::MAX;
const NODE: Cid = 0;
const WORLD: &str = "/";
const SEP: char = '/';

type Res<T> = Result<T, String>;

fn fallback<T>(why: &str) -> Res<T> {
    Err(why.to_string())
}

// Attr keys, in INTERNAL_ATTRS.ALL order, then the source metas of the
// tracked ones. comp_plan.native_build passes the names in this order.
pub const CODE: u8 = 0;
pub const EXECUTE_IN: u8 = 1;
pub const COMMENT: u8 = 2;
pub const START_POINT: u8 = 3;
pub const ENABLED: u8 = 4;
pub const INSTANCE: u8 = 5;
pub const CHILD_ORDER: u8 = 6;
pub const NAME: u8 = 7;
pub const SOURCE_LAYER: u8 = 8;
pub const PROXY: u8 = 9;
pub const PARENT_PATH: u8 = 10;
pub const NODE_PATH: u8 = 11;
pub const N_ATTRS: u8 = 12;
const TRACKED: [u8; 6] = [CODE, EXECUTE_IN, COMMENT, START_POINT, ENABLED, INSTANCE];
const ALL: [u8; 12] = [
    CODE, EXECUTE_IN, COMMENT, START_POINT, ENABLED, INSTANCE, CHILD_ORDER, NAME,
    SOURCE_LAYER, PROXY, PARENT_PATH, NODE_PATH,
];
// CompArc.INHERITANCE_MAP[INSTANCE], in its order.
const INSTANCE_OVERLOAD: [u8; 3] = [ENABLED, COMMENT, CODE];

fn meta(attr: u8) -> u8 {
    N_ATTRS + attr
}

// Python objects ------------------------------------------------------------

/// A Python str. Each Rc is one object.
pub type S = Rc<str>;

fn new_s(text: &str) -> S {
    Rc::from(text)
}

fn s_ptr(s: &S) -> usize {
    Rc::as_ptr(s) as *const u8 as usize
}

/// Whether CPython keeps one object for every string with this text: the
/// empty string, and one character strings up to U+00FF.
fn one_object(text: &str) -> bool {
    let mut chars = text.chars();
    match (chars.next(), chars.next()) {
        (None, _) => true,
        (Some(c), None) => (c as u32) < 256,
        _ => false,
    }
}

/// a is b, for strings.
fn same_str(a: &S, b: &S) -> bool {
    Rc::ptr_eq(a, b) || (**a == **b && one_object(a))
}

/// A Python list of strings, shared and changed in place as one is.
#[derive(Clone)]
pub struct SL(Rc<RefCell<Vec<S>>>);

impl SL {
    fn new(items: Vec<S>) -> SL {
        SL(Rc::new(RefCell::new(items)))
    }
    fn items(&self) -> Ref<'_, Vec<S>> {
        self.0.borrow()
    }
    fn ptr(&self) -> usize {
        Rc::as_ptr(&self.0) as *const u8 as usize
    }
    fn contains(&self, text: &str) -> bool {
        self.0.borrow().iter().any(|s| &**s == text)
    }
    fn is_empty(&self) -> bool {
        self.0.borrow().is_empty()
    }
}

/// Anything else, only ever passed on: whether it is an opinion and whether
/// it is truthy, worked out when it came in.
pub struct Opaque {
    has_op: bool,
    truthy: bool,
}

#[derive(Clone)]
pub enum Val {
    None,
    Bool(bool),
    Str(S),
    List(SL),
    Tuple(Rc<(Val, Val)>),
    Other(Rc<Opaque>),
}

impl Val {
    fn tuple(a: Val, b: Val) -> Val {
        Val::Tuple(Rc::new((a, b)))
    }
    /// nxt_node.has_opinion: value not in (None, []).
    fn has_opinion(&self) -> bool {
        match self {
            Val::None => false,
            Val::List(l) => !l.is_empty(),
            Val::Other(o) => o.has_op,
            _ => true,
        }
    }
    fn truthy(&self) -> bool {
        match self {
            Val::None => false,
            Val::Bool(b) => *b,
            Val::Str(s) => !s.is_empty(),
            Val::List(l) => !l.is_empty(),
            Val::Tuple(_) => true,
            Val::Other(o) => o.truthy,
        }
    }
    fn eq_str(&self, text: &str) -> bool {
        matches!(self, Val::Str(s) if &**s == text)
    }
    /// value is nxt_path.WORLD, which is any "/" in CPython.
    fn is_world(&self) -> bool {
        self.eq_str(WORLD)
    }
    fn list(&self) -> Res<SL> {
        match self {
            Val::List(l) => Ok(l.clone()),
            _ => fallback("a child order that is not a list of strings"),
        }
    }
    fn string(&self) -> Res<S> {
        match self {
            Val::Str(s) => Ok(s.clone()),
            _ => fallback("a path that is not a string"),
        }
    }
}

// What CPython's str methods give, object for object ------------------------

/// s[start:end], which is s itself when it is all of s.
fn substr(s: &S, start: usize, end: usize) -> S {
    if start == 0 && end == s.len() {
        s.clone()
    } else {
        new_s(&s[start..end])
    }
}

/// a + b, which is a when b is empty and b when a is.
fn concat(a: &S, b: &S) -> S {
    if b.is_empty() {
        return a.clone();
    }
    if a.is_empty() {
        return b.clone();
    }
    let mut text = String::with_capacity(a.len() + b.len());
    text.push_str(a);
    text.push_str(b);
    new_s(&text)
}

/// s.rpartition(sep) as (head, tail); ('', s) when sep is not in s.
fn rpartition(s: &S, sep: char) -> (S, S) {
    match s.rfind(sep) {
        None => (new_s(""), s.clone()),
        Some(i) => (substr(s, 0, i), substr(s, i + sep.len_utf8(), s.len())),
    }
}

/// s.split(sep), which is [s] when sep is not in s.
fn split(s: &S, sep: char) -> Vec<S> {
    if !s.contains(sep) {
        return vec![s.clone()];
    }
    s.split(sep).map(new_s).collect()
}

// nxt_path --------------------------------------------------------------------

fn expand_relative(rel: &S, start: &S) -> Option<S> {
    if rel.is_empty() {
        return None;
    }
    if &**rel == WORLD || rel.starts_with(SEP) {
        return Some(rel.clone());
    }
    let sep = new_s(WORLD);
    let mut current = start.clone();
    for directive in split(rel, SEP) {
        match &*directive {
            ".." => current = rpartition(&current, SEP).0,
            "." | "" => {}
            _ => current = concat(&concat(&current, &sep), &directive),
        }
    }
    Some(current)
}

fn get_parent_path(path: &S) -> S {
    if &**path == WORLD {
        return new_s("");
    }
    let (head, _) = rpartition(path, SEP);
    if head.is_empty() {
        new_s(WORLD)
    } else {
        head
    }
}

fn node_name_from_path(path: &S) -> S {
    if &**path == WORLD {
        return path.clone();
    }
    rpartition(path, SEP).1
}

fn path_depth(path: &str) -> usize {
    if path == WORLD {
        return 0;
    }
    path.matches(SEP).count()
}

fn join_node_paths(a: &S, b: &S) -> S {
    // '/'.join of two makes a new string; replace either hands that back or
    // makes another. New either way.
    new_s(&format!("{}{}{}", a, SEP, b).replace("//", "/"))
}

/// node_namespace_to_str_path: '/' + '/'.join(ns).
fn ns_to_path(ns: &[S]) -> S {
    let joined = match ns.len() {
        0 => new_s(""),
        1 => ns[0].clone(),
        _ => {
            let parts: Vec<&str> = ns.iter().map(|s| &**s).collect();
            new_s(&parts.join("/"))
        }
    };
    concat(&new_s(WORLD), &joined)
}

/// path_attr_partition(path)[0].
fn node_part(path: &S) -> S {
    if !path.contains('.') || path.ends_with('.') {
        return path.clone();
    }
    rpartition(path, '.').0
}

fn str_path_to_ns(path: &S) -> Vec<S> {
    let node = node_part(path);
    let parts = split(&node, SEP);
    if node.starts_with(SEP) {
        parts[1..].to_vec()
    } else {
        parts
    }
}

/// str_path_to_node_namespace(path)[-1], without making the rest.
fn ns_last(path: &S) -> S {
    let node = node_part(path);
    match node.rfind(SEP) {
        None => node,
        Some(i) => substr(&node, i + 1, node.len()),
    }
}

fn trim_to_depth(path: &S, depth: usize) -> S {
    if depth == 0 {
        return new_s(WORLD);
    }
    let given = path_depth(path);
    if given <= depth {
        return path.clone();
    }
    // path.rsplit(SEP, given - depth)[0]
    let remove = given - depth;
    let seps: Vec<usize> = path.match_indices(SEP).map(|(i, _)| i).collect();
    substr(path, 0, seps[seps.len() - remove])
}

fn is_ancestor(path: &str, ancestor: &str) -> bool {
    if ancestor == WORLD {
        return true;
    }
    path.len() > ancestor.len() && path.starts_with(ancestor) &&
        path.as_bytes()[ancestor.len()] == b'/'
}

/// nxt_node.list_merger, for lists of names.
fn list_merger(base: &[S], overlay: &[S]) -> Vec<S> {
    let mut merged: Vec<S> = base.to_vec();
    if base == overlay {
        return merged;
    }
    let src_set: HashSet<&str> = base.iter().map(|s| &**s).collect();
    let tgt_set: HashSet<&str> = overlay.iter().map(|s| &**s).collect();
    let tgt_order = overlay;
    let src_order = base;
    let only_source: Vec<S> = if tgt_set.intersection(&src_set).next().is_none() {
        src_order.iter().filter(|n| !tgt_order.contains(n)).cloned().collect()
    } else {
        Vec::new()
    };
    if tgt_set.is_subset(&src_set) {
        return merged;
    }
    for (idx, item) in tgt_order.iter().enumerate() {
        if src_set.contains(&**item) {
            continue;
        }
        if idx < src_order.len() {
            let mut offset = 0;
            let prev_idx = idx.saturating_sub(1);
            if src_order[prev_idx] != tgt_order[prev_idx] {
                let next_idx = idx + 1;
                if next_idx < src_order.len() && next_idx < tgt_order.len() &&
                        src_order[next_idx] == tgt_order[next_idx] {
                    offset = next_idx;
                }
            }
            let at = (idx + offset).min(merged.len());
            merged.insert(at, item.clone());
        } else {
            let at = idx.min(merged.len());
            merged.insert(at, item.clone());
        }
    }
    for item in only_source.iter().rev() {
        if let Some(pos) = merged.iter().position(|x| x == item) {
            merged.remove(pos);
        }
        merged.insert(0, item.clone());
    }
    merged
}

// Containers ----------------------------------------------------------------

/// An insertion ordered map, removal keeping order, like a Python dict: a
/// key set again keeps the key object it was first set with.
#[derive(Clone)]
struct OMap<K: std::hash::Hash + Eq + Clone, T> {
    index: HashMap<K, usize>,
    items: Vec<Option<(K, T)>>,
    len: usize,
}

impl<K: std::hash::Hash + Eq + Clone, T> Default for OMap<K, T> {
    fn default() -> Self {
        OMap { index: HashMap::new(), items: Vec::new(), len: 0 }
    }
}

impl<K: std::hash::Hash + Eq + Clone, T> OMap<K, T> {
    fn new() -> Self {
        Self::default()
    }
    fn get(&self, k: &K) -> Option<&T> {
        self.index.get(k).and_then(|&i| self.items[i].as_ref().map(|e| &e.1))
    }
    fn insert(&mut self, k: K, v: T) {
        if let Some(&i) = self.index.get(&k) {
            self.items[i].as_mut().unwrap().1 = v;
        } else {
            self.index.insert(k.clone(), self.items.len());
            self.items.push(Some((k, v)));
            self.len += 1;
        }
    }
    fn remove(&mut self, k: &K) -> Option<T> {
        let i = self.index.remove(k)?;
        self.len -= 1;
        self.items[i].take().map(|e| e.1)
    }
    fn iter(&self) -> impl Iterator<Item = (&K, &T)> {
        self.items.iter().filter_map(|e| e.as_ref().map(|(k, v)| (k, v)))
    }
    fn into_items(self) -> impl Iterator<Item = (K, T)> {
        self.items.into_iter().flatten()
    }
}

impl<T> OMap<S, T> {
    fn get_str(&self, k: &str) -> Option<&T> {
        self.index.get(k).and_then(|&i| self.items[i].as_ref().map(|e| &e.1))
    }
    fn get_str_mut(&mut self, k: &str) -> Option<&mut T> {
        match self.index.get(k) {
            Some(&i) => self.items[i].as_mut().map(|e| &mut e.1),
            None => None,
        }
    }
    fn contains_str(&self, k: &str) -> bool {
        self.index.contains_key(k)
    }
    fn remove_str(&mut self, k: &str) -> Option<T> {
        let i = self.index.remove(k)?;
        self.len -= 1;
        self.items[i].take().map(|e| e.1)
    }
}

/// nxt_layer.RankedList: a list of distinct items with index, remove and
/// insert in log time, items in per position buckets with a Fenwick tree
/// over the bucket sizes.
struct Ranked {
    buckets: Vec<Vec<usize>>,
    where_: HashMap<usize, usize>,
    tree: Vec<usize>,
    n: usize,
    total: usize,
}

impl Ranked {
    fn new(items: &[usize]) -> Ranked {
        let n = items.len();
        let mut tree = vec![0usize; n + 1];
        for i in 1..=n {
            tree[i] += 1;
            let parent = i + (i & i.wrapping_neg());
            if parent <= n {
                tree[parent] += tree[i];
            }
        }
        Ranked {
            buckets: items.iter().map(|&i| vec![i]).collect(),
            where_: items.iter().enumerate().map(|(b, &i)| (i, b)).collect(),
            tree,
            n,
            total: n,
        }
    }
    fn add(&mut self, bucket: usize, delta: isize) {
        let mut i = bucket + 1;
        while i <= self.n {
            self.tree[i] = (self.tree[i] as isize + delta) as usize;
            i += i & i.wrapping_neg();
        }
    }
    fn prefix(&self, bucket: usize) -> usize {
        let mut total = 0;
        let mut i = bucket;
        while i > 0 {
            total += self.tree[i];
            i -= i & i.wrapping_neg();
        }
        total
    }
    fn find(&self, rank: usize) -> (usize, usize) {
        let mut pos = 0;
        let mut remaining = rank;
        let mut step = 1;
        while step * 2 <= self.n {
            step *= 2;
        }
        while step > 0 {
            let next = pos + step;
            if next <= self.n && self.tree[next] <= remaining {
                pos = next;
                remaining -= self.tree[next];
            }
            step /= 2;
        }
        (pos, remaining)
    }
    fn index(&self, item: usize) -> usize {
        let bucket = self.where_[&item];
        let offset = self.buckets[bucket].iter().position(|&x| x == item).unwrap();
        self.prefix(bucket) + offset
    }
    fn remove(&mut self, item: usize) {
        let bucket = self.where_.remove(&item).unwrap();
        let at = self.buckets[bucket].iter().position(|&x| x == item).unwrap();
        self.buckets[bucket].remove(at);
        self.add(bucket, -1);
        self.total -= 1;
    }
    fn insert(&mut self, rank: usize, item: usize) {
        if self.n == 0 {
            self.buckets.push(vec![item]);
            self.n = 1;
            self.tree = vec![0, 1];
            self.where_.insert(item, 0);
            self.total += 1;
            return;
        }
        let bucket;
        if rank >= self.total {
            bucket = self.n - 1;
            self.buckets[bucket].push(item);
        } else {
            let (b, offset) = self.find(rank);
            if b >= self.n {
                bucket = self.n - 1;
                self.buckets[bucket].push(item);
            } else {
                bucket = b;
                self.buckets[bucket].insert(offset, item);
            }
        }
        self.where_.insert(item, bucket);
        self.add(bucket, 1);
        self.total += 1;
    }
    fn to_list(&self) -> Vec<usize> {
        self.buckets.iter().flatten().cloned().collect()
    }
}

// Classes -----------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq)]
enum Kind {
    Node,
    Spec,
    MadeSpec,
    Comp,
}

/// A class's own attrs: a slot per key, and the order they were first set,
/// which is the order Python's class dict keeps them in.
#[derive(Clone)]
struct Slots {
    vals: Vec<Option<Val>>,
    order: Vec<u8>,
}

const N_KEYS: usize = (N_ATTRS as usize) * 2;

impl Slots {
    fn from_vec(items: Vec<(u8, Val)>) -> Slots {
        let mut slots = Slots { vals: vec![None; N_KEYS], order: Vec::with_capacity(items.len()) };
        for (k, v) in items {
            slots.set(k, v);
        }
        slots
    }
    fn get(&self, k: u8) -> Option<&Val> {
        self.vals[k as usize].as_ref()
    }
    fn set(&mut self, k: u8, v: Val) {
        if self.vals[k as usize].is_none() {
            self.order.push(k);
        }
        self.vals[k as usize] = Some(v);
    }
    fn iter(&self) -> impl Iterator<Item = (u8, &Val)> {
        self.order.iter().map(move |&k| (k, self.vals[k as usize].as_ref().unwrap()))
    }
}

struct Class {
    kind: Kind,
    dict: Slots,
    // How many of dict's keys the class was made with; they come first.
    n_initial: usize,
    bases: Vec<Cid>,
    subs: HashSet<Cid>,
    mro: Option<Rc<Vec<Cid>>>,
    spec_index: usize,
}

/// A child cache entry, as CompLayer keeps one.
#[derive(Clone, Default)]
struct Entry {
    nodes: Vec<Cid>,
    paths: Vec<S>,
    table: Vec<(S, Cid)>,
    names: OMap<S, Cid>,
}

pub struct Log {
    pub level: &'static str,
    pub msg: String,
    pub links: Vec<String>,
}

pub struct Plan {
    classes: Vec<Class>,
    comp_real_path: Val,
    // source layer value -> the real_path of the layer stage.lookup_layer
    // finds for it, or None when it finds none.
    layers: HashMap<String, Option<Val>>,
    overload_order: Vec<u8>,
    pub logs: Vec<Log>,
    pub layer_calls: Vec<(String, String)>,
    path_key: OMap<S, Cid>,
    node_key: OMap<Cid, S>,
    node_table: Vec<(SL, Cid)>,
    cached_children: OMap<S, Entry>,
    cached_implied: OMap<S, Vec<S>>,
    bulk_valid: bool,
    implied_index: OMap<S, Vec<S>>,
    implied_valid: bool,
    implied_len: i64,
    dirty_map: OMap<S, Vec<S>>,
    strict: bool,
    // Python objects read in: the value made for each object, so an object
    // read twice is one value, and the object each value was read from.
    read: HashMap<usize, Val>,
    objects: HashMap<usize, Py<PyAny>>,
    read_lists: Vec<(SL, Vec<S>)>,
    pub timers: RefCell<HashMap<&'static str, std::time::Duration>>,
}

macro_rules! timed {
    ($self:ident, $name:expr, $body:expr) => {{
        let __t = std::time::Instant::now();
        let __r = $body;
        *$self.timers.borrow_mut().entry($name).or_default() += __t.elapsed();
        __r
    }};
}

impl Plan {
    pub fn new(overload_order: Vec<u8>, strict: bool) -> Plan {
        Plan {
            classes: Vec::new(),
            comp_real_path: Val::None,
            layers: HashMap::new(),
            overload_order,
            logs: Vec::new(),
            layer_calls: Vec::new(),
            path_key: OMap::new(),
            node_key: OMap::new(),
            node_table: Vec::new(),
            cached_children: OMap::new(),
            cached_implied: OMap::new(),
            bulk_valid: false,
            implied_index: OMap::new(),
            implied_valid: false,
            implied_len: -1,
            dirty_map: OMap::new(),
            strict,
            read: HashMap::new(),
            objects: HashMap::new(),
            read_lists: Vec::new(),
            timers: RefCell::new(HashMap::new()),
        }
    }

    pub fn print_timing(&self) {
        let mut items: Vec<_> = self.timers.borrow().iter().map(|(k, v)| (*k, *v)).collect();
        items.sort_by_key(|i| std::cmp::Reverse(i.1));
        for (k, v) in items {
            eprintln!("  {:24} {:?}", k, v);
        }
    }

    pub fn set_comp_layer(&mut self, real_path: Val, layers: HashMap<String, Option<Val>>) {
        self.comp_real_path = real_path;
        self.layers = layers;
    }

    // Reading Python objects ------------------------------------------------------

    fn remember(&mut self, ptr: usize, obj: &Bound<'_, PyAny>) {
        self.objects.insert(ptr, obj.clone().unbind());
    }

    /// A Python object as a value: the same value each time for the same
    /// object, and handed back as that object at the end.
    pub fn to_val(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<Val> {
        let key = obj.as_ptr() as usize;
        if let Some(v) = self.read.get(&key) {
            return Ok(v.clone());
        }
        let v = if obj.is_none() {
            Val::None
        } else if let Ok(b) = obj.downcast_exact::<PyBool>() {
            Val::Bool(b.is_true())
        } else if let Ok(s) = obj.downcast_exact::<PyString>() {
            let s = new_s(s.to_str()?);
            self.remember(s_ptr(&s), obj);
            Val::Str(s)
        } else if let Some(items) = self.str_items(obj)? {
            let list = SL::new(items.clone());
            self.remember(list.ptr(), obj);
            self.read_lists.push((list.clone(), items));
            Val::List(list)
        } else if let Ok(t) = obj.downcast_exact::<PyTuple>() {
            if t.len() == 2 {
                let a = self.to_val(&t.get_item(0)?)?;
                let b = self.to_val(&t.get_item(1)?)?;
                let pair = Rc::new((a, b));
                self.remember(Rc::as_ptr(&pair) as *const u8 as usize, obj);
                Val::Tuple(pair)
            } else {
                self.other(obj, true, t.len() > 0)
            }
        } else {
            // has_opinion: not None and not == []; only lists equal [].
            let empty_list = PyList::empty(obj.py());
            let eq_empty = obj.eq(&empty_list).unwrap_or(false);
            let truthy = obj.is_truthy().unwrap_or(true);
            self.other(obj, !eq_empty, truthy)
        };
        self.read.insert(key, v.clone());
        Ok(v)
    }

    fn other(&mut self, obj: &Bound<'_, PyAny>, has_op: bool, truthy: bool) -> Val {
        let o = Rc::new(Opaque { has_op, truthy });
        self.remember(Rc::as_ptr(&o) as *const u8 as usize, obj);
        Val::Other(o)
    }

    /// A list's items as strings, each read as itself, when it is a list of
    /// nothing but strings.
    fn str_items(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<Option<Vec<S>>> {
        let l = match obj.downcast_exact::<PyList>() {
            Ok(l) => l,
            Err(_) => return Ok(None),
        };
        let mut items = Vec::with_capacity(l.len());
        for item in l.iter() {
            if item.downcast_exact::<PyString>().is_err() {
                return Ok(None);
            }
            match self.to_val(&item)? {
                Val::Str(s) => items.push(s),
                _ => return Ok(None),
            }
        }
        Ok(Some(items))
    }

    // Classes -----------------------------------------------------------------

    pub fn add_node_class(&mut self, dict: Vec<(u8, Val)>) {
        self.classes.push(Class {
            kind: Kind::Node,
            dict: Slots::from_vec(dict),
            n_initial: 0,
            bases: Vec::new(),
            subs: HashSet::new(),
            mro: Some(Rc::new(vec![NODE, OBJECT])),
            spec_index: 0,
        });
    }

    pub fn add_spec_class(&mut self, spec_index: usize, dict: Vec<(u8, Val)>) -> Cid {
        let cid = self.classes.len();
        self.classes.push(Class {
            kind: Kind::Spec,
            dict: Slots::from_vec(dict),
            n_initial: 0,
            bases: vec![NODE],
            subs: HashSet::new(),
            mro: Some(Rc::new(vec![cid, NODE, OBJECT])),
            spec_index,
        });
        cid
    }

    fn new_class(&mut self, kind: Kind, bases: Vec<Cid>, attrs: Vec<(u8, Val)>) -> Res<Cid> {
        let cid = self.classes.len();
        for &b in &bases {
            if b != OBJECT {
                self.classes[b].subs.insert(cid);
            }
        }
        let dict = Slots::from_vec(attrs);
        let n_initial = dict.order.len();
        self.classes.push(Class {
            kind,
            dict,
            n_initial,
            bases,
            subs: HashSet::new(),
            mro: None,
            spec_index: 0,
        });
        self.mro(cid)?;
        Ok(cid)
    }

    fn mro(&mut self, cid: Cid) -> Res<Rc<Vec<Cid>>> {
        if cid == OBJECT {
            return Ok(Rc::new(vec![OBJECT]));
        }
        if let Some(m) = &self.classes[cid].mro {
            return Ok(m.clone());
        }
        let result = Rc::new(timed!(self, "c3", self.c3(cid))?);
        self.classes[cid].mro = Some(result.clone());
        Ok(result)
    }

    fn c3(&mut self, cid: Cid) -> Res<Vec<Cid>> {
        // CPython's merge: take the head of the first list, in order, that
        // is in no list's tail. How many tails hold each class is counted,
        // rather than looked for, but the same head is taken every step.
        let bases = self.classes[cid].bases.clone();
        let unique: HashSet<Cid> = bases.iter().cloned().collect();
        if unique.len() != bases.len() {
            return fallback("duplicate base class");
        }
        let mut seqs: Vec<Rc<Vec<Cid>>> = Vec::with_capacity(bases.len() + 1);
        for &b in &bases {
            seqs.push(self.mro(b)?);
        }
        seqs.push(Rc::new(bases));
        let mut pos: Vec<usize> = vec![0; seqs.len()];
        let mut in_tails: HashMap<Cid, usize> = HashMap::new();
        let mut total = 0usize;
        for seq in &seqs {
            total += seq.len();
            for &c in seq.iter().skip(1) {
                *in_tails.entry(c).or_insert(0) += 1;
            }
        }
        let mut result = Vec::with_capacity(total + 1);
        result.push(cid);
        loop {
            let mut head = None;
            let mut any = false;
            for i in 0..seqs.len() {
                if pos[i] >= seqs[i].len() {
                    continue;
                }
                any = true;
                let candidate = seqs[i][pos[i]];
                if in_tails.get(&candidate).copied().unwrap_or(0) == 0 {
                    head = Some(candidate);
                    break;
                }
            }
            if !any {
                return Ok(result);
            }
            let head = match head {
                Some(h) => h,
                None => return fallback("inconsistent method resolution order"),
            };
            result.push(head);
            for i in 0..seqs.len() {
                if pos[i] < seqs[i].len() && seqs[i][pos[i]] == head {
                    pos[i] += 1;
                    if pos[i] < seqs[i].len() {
                        let next = seqs[i][pos[i]];
                        if let Some(n) = in_tails.get_mut(&next) {
                            *n -= 1;
                        }
                    }
                }
            }
        }
    }

    fn set_bases(&mut self, cid: Cid, new_bases: Vec<Cid>) -> Res<()> {
        if new_bases.is_empty() {
            return fallback("empty bases");
        }
        for &b in &new_bases {
            if b != OBJECT && self.mro(b)?.contains(&cid) {
                return fallback("inheritance cycle");
            }
        }
        let old = std::mem::take(&mut self.classes[cid].bases);
        for b in old {
            if b != OBJECT {
                self.classes[b].subs.remove(&cid);
            }
        }
        for &b in &new_bases {
            if b != OBJECT {
                self.classes[b].subs.insert(cid);
            }
        }
        self.classes[cid].bases = new_bases;
        self.forget_mro(cid);
        self.mro(cid)?;
        if self.strict {
            self.check_subclasses(cid)?;
        }
        Ok(())
    }

    fn forget_mro(&mut self, cid: Cid) {
        let mut stack = vec![cid];
        let mut seen = HashSet::new();
        while let Some(c) = stack.pop() {
            if !seen.insert(c) {
                continue;
            }
            if self.classes[c].kind == Kind::Comp || self.classes[c].kind == Kind::MadeSpec {
                self.classes[c].mro = None;
            }
            stack.extend(self.classes[c].subs.iter().cloned());
        }
    }

    fn check_subclasses(&mut self, cid: Cid) -> Res<()> {
        let subs: Vec<Cid> = self.classes[cid].subs.iter().cloned().collect();
        for s in subs {
            self.mro(s)?;
            self.check_subclasses(s)?;
        }
        Ok(())
    }

    fn lookup_attr(&mut self, cid: Cid, attr: u8) -> Res<Option<Val>> {
        let mro = self.mro(cid)?;
        for &c in mro.iter() {
            if c == OBJECT {
                continue;
            }
            if let Some(v) = self.classes[c].dict.get(attr) {
                return Ok(Some(v.clone()));
            }
        }
        Ok(None)
    }

    /// getattr(cls, attr, None)
    fn get(&mut self, cid: Option<Cid>, attr: u8) -> Res<Val> {
        match cid {
            None => Ok(Val::None),
            Some(c) => Ok(self.lookup_attr(c, attr)?.unwrap_or(Val::None)),
        }
    }

    /// getattr(cls, attr), which raises when there is none.
    fn must(&mut self, cid: Cid, attr: u8) -> Res<Val> {
        match self.lookup_attr(cid, attr)? {
            Some(v) => Ok(v),
            None => fallback("a class without an attr asked for"),
        }
    }

    fn set(&mut self, cid: Cid, attr: u8, val: Val) -> Res<()> {
        let class = &mut self.classes[cid];
        if class.kind == Kind::Node || class.kind == Kind::Spec {
            return fallback("setting an attr on an existing class");
        }
        class.dict.set(attr, val);
        Ok(())
    }

    fn name(&mut self, cid: Cid) -> Res<S> {
        match self.must(cid, NAME)? {
            Val::Str(s) => Ok(s),
            _ => fallback("a node name that is not a string"),
        }
    }

    fn is_comp(&self, cid: Cid) -> bool {
        self.classes[cid].kind == Kind::Comp
    }

    fn log(&mut self, level: &'static str, msg: String, links: Vec<String>) {
        self.logs.push(Log { level, msg, links });
    }

    // The comp layer, as CompLayer keeps it -----------------------------------------

    fn lookup(&self, path: &str) -> Option<Cid> {
        self.path_key.get_str(path).cloned()
    }

    /// path_key.get(value), for a value that may not be a string.
    fn lookup_val(&self, path: &Val) -> Res<Option<Cid>> {
        match path {
            Val::Str(s) => Ok(self.lookup(s)),
            Val::None | Val::Bool(_) | Val::Tuple(_) => Ok(None),
            _ => fallback("looking up a path that may not hash"),
        }
    }

    fn node_path(&self, cid: Cid) -> Res<S> {
        match self.node_key.get(&cid) {
            Some(p) => Ok(p.clone()),
            None => fallback("a node not in the comp layer"),
        }
    }

    /// Whether target is in get_node_dirties(node_path).
    fn dirties_hold(&self, node_path: &str, target: &str) -> bool {
        let start: Vec<S> = self.dirty_map.get_str(node_path).cloned().unwrap_or_default();
        let mut concerns: HashSet<&str> = start.iter().map(|s| &**s).collect();
        if concerns.contains(target) {
            return true;
        }
        let mut frontier: Vec<&str> = vec![node_path];
        frontier.extend(start.iter().map(|s| &**s));
        while !frontier.is_empty() {
            let mut next: Vec<&str> = Vec::new();
            for concern in &frontier {
                if let Some(found) = self.dirty_map.get_str(concern) {
                    for item in found {
                        if concerns.insert(&**item) {
                            if &**item == target {
                                return true;
                            }
                            next.push(&**item);
                        }
                    }
                }
            }
            frontier = next;
        }
        false
    }

    fn extend_dirty_map(&mut self, node_path: &S, concern: &S) {
        if &**node_path == WORLD || &**concern == WORLD {
            return;
        }
        if !self.dirty_map.contains_str(node_path) {
            self.dirty_map.insert(node_path.clone(), Vec::new());
        }
        // An empty list already there is put back in its own place.
        if !same_str(concern, node_path) {
            let list = self.dirty_map.get_str_mut(node_path).unwrap();
            if !list.iter().any(|c| **c == **concern) {
                list.push(concern.clone());
            }
        }
    }

    fn clear_node_child_cache(&mut self, path: &str) {
        self.bulk_valid = false;
        self.implied_valid = false;
        self.cached_children.remove_str(path);
        self.cached_implied.remove_str(path);
    }

    fn add_child_to_child_cache(&mut self, parent: &Val, child_path: &S, child: Cid) -> Res<()> {
        if !parent.truthy() || parent.is_world() {
            return Ok(());
        }
        let parent = parent.string()?;
        let name = self.name(child)?;
        // Python puts a copy with the child added in the old entry's place.
        // Nothing else holds the old one, so adding to it is the same.
        if !self.cached_children.contains_str(&parent) {
            self.cached_children.insert(parent.clone(), Entry::default());
        }
        let entry = self.cached_children.get_str_mut(&parent).unwrap();
        entry.nodes.push(child);
        entry.paths.push(child_path.clone());
        entry.table.push((child_path.clone(), child));
        entry.names.insert(name, child);
        Ok(())
    }

    fn remove_child_from_child_cache(&mut self, parent: &Val, child_path: &S, child: Cid) -> Res<()> {
        if parent.is_world() {
            return Ok(());
        }
        let parent = match parent {
            Val::None => return Ok(()),
            v => v.string()?,
        };
        if !self.cached_children.contains_str(&parent) {
            return Ok(());
        }
        let name = self.name(child)?;
        let entry = self.cached_children.get_str_mut(&parent).unwrap();
        if let Some(i) = entry.nodes.iter().position(|&c| c == child) {
            entry.nodes.remove(i);
        }
        if let Some(i) = entry.paths.iter().position(|p| **p == **child_path) {
            entry.paths.remove(i);
        }
        if let Some(i) = entry.table.iter().position(|(p, c)| **p == **child_path && *c == child) {
            entry.table.remove(i);
        }
        entry.names.remove(&name);
        Ok(())
    }

    fn build_child_cache(&mut self) -> Res<()> {
        let mut cache: OMap<S, Entry> = OMap::new();
        let items: Vec<(S, Cid)> = self.path_key.iter().map(|(p, c)| (p.clone(), *c)).collect();
        for (path, _) in &items {
            if &**path != WORLD {
                cache.insert(path.clone(), Entry::default());
            }
        }
        for (path, node) in &items {
            let parent = self.must(*node, PARENT_PATH)?;
            if !parent.truthy() || parent.is_world() {
                continue;
            }
            let parent = parent.string()?;
            if !cache.contains_str(&parent) {
                cache.insert(parent.clone(), Entry::default());
            }
            let name = self.name(*node)?;
            let entry = cache.get_str_mut(&parent).unwrap();
            entry.nodes.push(*node);
            entry.paths.push(path.clone());
            entry.table.push((path.clone(), *node));
            entry.names.insert(name, *node);
        }
        // As CompLayer._build_child_cache: only paths with no entry yet.
        for (path, entry) in cache.into_items() {
            if !self.cached_children.contains_str(&path) {
                self.cached_children.insert(path, entry);
            }
        }
        self.bulk_valid = true;
        Ok(())
    }

    fn build_implied_index(&mut self) {
        let mut index: OMap<S, Vec<S>> = OMap::new();
        let mut seen: HashMap<String, HashSet<String>> = HashMap::new();
        for (path, _) in self.path_key.iter() {
            if &**path == WORLD {
                continue;
            }
            // parts = path.split('/'); '/'.join(parts[:k]) is the path up to
            // its k-th separator, always a new string for k >= 2.
            let seps: Vec<usize> = path.match_indices(SEP).map(|(i, _)| i).collect();
            let n_parts = seps.len() + 1;
            for depth in 1..n_parts.saturating_sub(1) {
                let ancestor = &path[..seps[depth]];
                let trimmed = if depth + 1 < seps.len() { &path[..seps[depth + 1]] } else { &path[..] };
                if !index.contains_str(ancestor) {
                    index.insert(new_s(ancestor), Vec::new());
                    seen.insert(ancestor.to_string(), HashSet::new());
                }
                if seen.get_mut(ancestor).unwrap().insert(trimmed.to_string()) {
                    index.get_str_mut(ancestor).unwrap().push(new_s(trimmed));
                }
            }
        }
        self.implied_index = index;
        self.implied_len = self.path_key.len as i64;
        self.implied_valid = true;
    }

    fn implied_children_for(&mut self, path: &str) -> Vec<S> {
        if !self.implied_valid || self.implied_len != self.path_key.len as i64 {
            self.build_implied_index();
        }
        self.implied_index.get_str(path).cloned().unwrap_or_default()
    }

    /// CompLayer.children, unordered: the paths, and the name dict.
    fn children(&mut self, node_path: &Val, include_implied: bool)
        -> Res<(Vec<S>, OMap<S, Cid>)> {
        if !node_path.truthy() {
            return Ok((Vec::new(), OMap::new()));
        }
        let node_path = node_path.string()?;
        let world = &*node_path == WORLD;
        let mut hit = !world && self.cached_children.contains_str(&node_path);
        if !world && !hit && !self.bulk_valid {
            self.build_child_cache()?;
            hit = self.cached_children.contains_str(&node_path);
        }
        let cache_real = !hit;
        let mut entry = Entry::default();
        let mut paths: Vec<S> = Vec::new();
        if hit {
            let cached = self.cached_children.get_str(&node_path).unwrap();
            paths = cached.paths.clone();
            entry.names = cached.names.clone();
        }
        let mut implied: Vec<S> = Vec::new();
        let mut cache_implied = false;
        if include_implied {
            let found = if world { None } else { self.cached_implied.get_str(&node_path).cloned() };
            if let Some(c) = found {
                implied = c;
            } else if !world {
                implied = self.implied_children_for(&node_path);
                self.cached_implied.insert(node_path.clone(), implied.clone());
            } else {
                cache_implied = true;
            }
        }
        if cache_implied || cache_real {
            let prefix = format!("{}{}", node_path, SEP);
            let trim_depth = path_depth(&node_path) + 1;
            let mut seen_implied: HashSet<S> = HashSet::new();
            let items: Vec<(S, Cid)> = self.path_key.iter().map(|(p, c)| (p.clone(), *c)).collect();
            for (path, node) in items {
                if cache_real {
                    let parent = self.must(node, PARENT_PATH)?;
                    if parent.eq_str(&node_path) {
                        let name = self.name(node)?;
                        entry.nodes.push(node);
                        paths.push(path.clone());
                        entry.table.push((path.clone(), node));
                        entry.names.insert(name, node);
                    }
                }
                if !include_implied || !cache_implied {
                    continue;
                }
                if !world && !path.starts_with(&prefix) {
                    continue;
                }
                let trimmed = trim_to_depth(&path, trim_depth);
                if seen_implied.insert(trimmed.clone()) {
                    implied.push(trimmed);
                }
            }
            if cache_implied {
                self.cached_implied.insert(node_path.clone(), implied.clone());
            }
        }
        if cache_real {
            entry.paths = paths.clone();
            let names = entry.names.clone();
            self.cached_children.insert(node_path.clone(), entry);
            entry = Entry { names, ..Entry::default() };
        }
        if include_implied {
            let mut have: HashSet<S> = paths.iter().cloned().collect();
            for imp in implied {
                if have.insert(imp.clone()) {
                    paths.push(imp);
                }
            }
        }
        Ok((paths, entry.names))
    }

    // Stage helpers -----------------------------------------------------------------

    fn add_node_to_comp_layer(&mut self, path: &S, node: Cid, ns: SL,
                              add_to_child_order: bool) -> Res<Cid> {
        let node = if self.is_comp(node) { node } else {
            self.new_class(Kind::Comp, vec![node], Vec::new())?
        };
        let name = self.name(node)?;
        self.node_table.push((ns, node));
        self.path_key.insert(path.clone(), node);
        self.node_key.insert(node, path.clone());
        let parent_path = self.must(node, PARENT_PATH)?;
        self.add_child_to_child_cache(&parent_path, path, node)?;
        if add_to_child_order {
            if let Some(parent_node) = self.lookup_val(&parent_path)? {
                let co = self.must(parent_node, CHILD_ORDER)?.list()?;
                if !co.contains(&name) {
                    let merged = list_merger(&co.items(), &[name]);
                    self.set(parent_node, CHILD_ORDER, Val::List(SL::new(merged)))?;
                }
            }
        }
        Ok(node)
    }

    fn remove_node_from_comp_layer(&mut self, path: &S, node: Option<Cid>, ns: &SL) -> Res<()> {
        let node = match node {
            Some(n) if self.is_comp(n) => n,
            _ => return fallback("removing a node that is not a comp node"),
        };
        let parent = self.must(node, PARENT_PATH)?;
        let at = self.node_table.iter().position(|(n, c)| *c == node && *n.items() == *ns.items());
        match at {
            Some(i) => {
                self.node_table.remove(i);
            }
            None => return fallback("a node not in the node table"),
        }
        if self.path_key.remove_str(path).is_none() {
            return fallback("a path not in the comp layer");
        }
        if self.node_key.remove(&node).is_none() {
            return fallback("a node not in the comp layer");
        }
        self.clear_node_child_cache(path);
        self.remove_child_from_child_cache(&parent, path, node)
    }

    /// create_spec_node, on the comp layer (layer None) or a real layer (the
    /// value of its real_path).
    fn create_spec_node(&mut self, data: &[(u8, Val)], layer: Option<Val>,
                        parent: &S, is_proxy: bool) -> Res<Cid> {
        let get = |key: u8| -> Val {
            data.iter().find(|(k, _)| *k == key).map(|(_, v)| v.clone()).unwrap_or(Val::None)
        };
        let node_name = get(NAME);
        let name_s = match &node_name {
            Val::Str(s) => s.clone(),
            _ => return fallback("a made node without a name"),
        };
        let layer_real_path = match &layer {
            None => self.comp_real_path.clone(),
            Some(v) => v.clone(),
        };
        let path = join_node_paths(parent, &name_s);
        let mut attrs: Vec<(u8, Val)> = Vec::with_capacity(ALL.len());
        for &attr in ALL.iter() {
            let mut val = get(attr);
            if !val.has_opinion() && attr != ENABLED {
                val = match attr {
                    CODE => Val::List(SL::new(Vec::new())),
                    PARENT_PATH => Val::Str(new_s(WORLD)),
                    _ => Val::None,
                };
            }
            attrs.push((attr, val));
        }
        let set = |attrs: &mut Vec<(u8, Val)>, k: u8, v: Val| {
            for item in attrs.iter_mut() {
                if item.0 == k {
                    item.1 = v;
                    return;
                }
            }
            attrs.push((k, v));
        };
        set(&mut attrs, NAME, node_name.clone());
        set(&mut attrs, PROXY, Val::Bool(is_proxy));
        set(&mut attrs, CHILD_ORDER, Val::List(SL::new(Vec::new())));
        set(&mut attrs, SOURCE_LAYER, layer_real_path.clone());
        let pp = if is_proxy {
            let given = get(PARENT_PATH);
            if given.truthy() { given } else { Val::Str(parent.clone()) }
        } else {
            Val::Str(parent.clone())
        };
        set(&mut attrs, PARENT_PATH, pp);
        let spec = self.new_class(Kind::MadeSpec, vec![NODE], attrs)?;
        match &layer {
            None => {
                let parent_object = self.lookup(parent);
                self.clear_node_child_cache(&path);
                self.clear_node_child_cache(parent);
                if let Some(po) = parent_object {
                    let proxies = self.must(spec, PROXY)?.truthy() || self.must(po, PROXY)?.truthy();
                    let co = self.must(po, CHILD_ORDER)?.list()?;
                    if !co.contains(&name_s) && !proxies {
                        let merged = list_merger(&co.items(), &[name_s.clone()]);
                        self.set(po, CHILD_ORDER, Val::List(SL::new(merged)))?;
                    }
                }
            }
            Some(real) => {
                // Only proxies are made on real layers, which leave the
                // parent's child order alone; the cache clears are replayed.
                if !is_proxy {
                    return fallback("a spec node made on a real layer");
                }
                let layer_text = real.string()?.to_string();
                self.layer_calls.push((layer_text.clone(), path.to_string()));
                self.layer_calls.push((layer_text, parent.to_string()));
            }
        }
        for &attr in TRACKED.iter() {
            // A new tuple each time round, as in Python.
            self.set(spec, meta(attr), Val::tuple(layer_real_path.clone(), Val::Str(path.clone())))?;
        }
        Ok(spec)
    }

    // The comp ------------------------------------------------------------------------

    pub fn comp_pre_proxies(&mut self, tables: &[Vec<(SL, Cid)>]) -> Res<usize> {
        let mut node_count = 0;
        let mut base_mapping: OMap<S, Vec<Cid>> = OMap::new();
        for table in tables {
            for (ns, spec) in table {
                let path = ns_to_path(&ns.items());
                let stronger = self.lookup(&path);
                // bases = base_mapping.get(path, []); bases += [spec]
                let bases = match base_mapping.get_str_mut(&path) {
                    Some(b) => {
                        b.push(*spec);
                        b.clone()
                    }
                    None => vec![*spec],
                };
                if stronger.is_some() {
                    continue;
                }
                let name = self.must(*spec, NAME)?;
                let comp = self.new_class(Kind::Comp, vec![*spec], vec![(NAME, name)])?;
                self.add_node_to_comp_layer(&path, comp, ns.clone(), false)?;
                base_mapping.insert(path, bases);
                node_count += 1;
            }
        }
        let overload = self.overload_order.clone();
        let items: Vec<(S, Vec<Cid>)> = base_mapping.iter().map(|(p, b)| (p.clone(), b.clone())).collect();
        for (path, bases) in items {
            let comp = match self.lookup(&path) {
                Some(c) => c,
                None => return fallback("a mapped path not in the comp layer"),
            };
            if bases != self.classes[comp].bases {
                self.set_bases(comp, bases.clone())?;
            }
            for (idx, &spec) in bases.iter().rev().enumerate() {
                if idx == 0 {
                    let co = self.must(spec, CHILD_ORDER)?;
                    self.set(comp, CHILD_ORDER, co)?;
                }
                for &attr in &overload {
                    let value = self.get(Some(spec), attr)?;
                    if value.has_opinion() {
                        let src_layer = self.must(spec, SOURCE_LAYER)?;
                        self.set(comp, attr, value)?;
                        self.set(comp, meta(attr), Val::tuple(src_layer, Val::Str(path.clone())))?;
                    }
                }
                if &*path == WORLD {
                    continue;
                }
                let spec_co = self.must(spec, CHILD_ORDER)?.list()?;
                let comp_co = self.must(comp, CHILD_ORDER)?.list()?;
                let merged = list_merger(&spec_co.items(), &comp_co.items());
                self.set(comp, CHILD_ORDER, Val::List(SL::new(merged)))?;
            }
        }
        Ok(node_count)
    }

    /// stage.lookup_layer(value).real_path, None when there is no layer.
    fn layer_for(&self, source_layer: &Val) -> Res<Option<Val>> {
        match source_layer {
            Val::Str(s) => match self.layers.get(&**s) {
                Some(found) => Ok(found.clone()),
                None => fallback("a source layer the stage was not asked about"),
            },
            _ => Ok(None),
        }
    }

    /// Some(node), or None where Python returns False.
    fn create_instance_node(&mut self, source_path: &S, tgt_path: &S, new_tgt_ns: SL)
        -> Res<Option<Cid>> {
        let mut implied = false;
        let mut force_source_layer = false;
        let inst_source = match self.lookup(source_path) {
            Some(c) => c,
            None => {
                let node_name = node_name_from_path(source_path);
                let inst_pp = get_parent_path(source_path);
                let inst_parent = self.lookup(&inst_pp);
                let p_inst = self.get(inst_parent, INSTANCE)?;
                let (_, inst_children) = self.children(&p_inst, false)?;
                let data = [(NAME, Val::Str(node_name.clone()))];
                let spec = self.create_spec_node(&data, None, &inst_pp, false)?;
                if inst_children.contains_str(&node_name) {
                    force_source_layer = true;
                } else {
                    implied = true;
                }
                spec
            }
        };
        let target_parent = get_parent_path(tgt_path);
        let existing = self.lookup(tgt_path);
        let src_layer_val = self.must(inst_source, SOURCE_LAYER)?;
        let layer = match self.layer_for(&src_layer_val)? {
            Some(l) => l,
            None => return fallback("instance source layer not in the stage"),
        };
        let node = match existing {
            None => {
                let data = [
                    (NAME, self.must(inst_source, NAME)?),
                    (COMMENT, self.must(inst_source, COMMENT)?),
                    (ENABLED, self.must(inst_source, ENABLED)?),
                    (SOURCE_LAYER, self.must(inst_source, SOURCE_LAYER)?),
                    (PARENT_PATH, Val::Str(target_parent.clone())),
                ];
                let spec = self.create_spec_node(&data, Some(layer), &target_parent, true)?;
                let new_target = self.new_class(Kind::Comp, vec![spec], Vec::new())?;
                self.add_node_to_comp_layer(tgt_path, new_target, new_tgt_ns, true)?;
                let parent_node = match self.lookup(&target_parent) {
                    Some(n) => n,
                    None => return fallback("a proxy without a parent node"),
                };
                let parent_layer = self.must(parent_node, SOURCE_LAYER)?;
                if force_source_layer {
                    self.set(new_target, SOURCE_LAYER, parent_layer.clone())?;
                }
                self.set(new_target, INSTANCE, Val::Str(source_path.clone()))?;
                self.set(new_target, meta(INSTANCE), Val::tuple(parent_layer, Val::Str(source_path.clone())))?;
                new_target
            }
            Some(existing) => {
                self.set(existing, INSTANCE, Val::Str(source_path.clone()))?;
                self.set(existing, meta(INSTANCE), Val::tuple(layer, Val::Str(source_path.clone())))?;
                existing
            }
        };
        self.extend_dirty_map(source_path, tgt_path);
        Ok(if implied { None } else { Some(node) })
    }

    /// The instance path a node may take, for discover_proxies and
    /// instance_is_possible, logging why not when it may not.
    fn checked_instance(&mut self, node_path: &S, node: Cid) -> Res<Option<S>> {
        let instance = self.get(Some(node), INSTANCE)?;
        if !instance.truthy() {
            return Ok(None);
        }
        if instance.is_world() {
            self.log("error", format!("Invalid instance path on {}", node_path), vec![node_path.to_string()]);
            return Ok(None);
        }
        let instance = instance.string()?;
        let real = expand_relative(&instance, node_path).unwrap_or_else(|| new_s(""));
        if node_path.len() > real.len() && node_path.starts_with(&*real) &&
                node_path.as_bytes()[real.len()] == b'/' {
            self.log("error", format!("{} attempted to instance an ancestor!", node_path),
                     vec![node_path.to_string()]);
            return Ok(None);
        }
        if timed!(self, "get_node_dirties", self.dirties_hold(node_path, &real)) {
            self.log("error", format!("{} attempted to instance dependant!", node_path),
                     vec![node_path.to_string()]);
            return Ok(None);
        }
        Ok(Some(real))
    }

    fn discover_proxies(&mut self, node_path: &S, node: Cid, namespace: &SL)
        -> Res<Vec<(SL, S, S)>> {
        let mut to_do = Vec::new();
        let real = match self.checked_instance(node_path, node)? {
            Some(r) => r,
            None => return Ok(to_do),
        };
        self.set(node, INSTANCE, Val::Str(real.clone()))?;
        self.extend_dirty_map(&real, node_path);
        if let Some(src) = self.lookup(&real) {
            let comp_co = self.must(node, CHILD_ORDER)?.list()?;
            let inst_co = self.must(src, CHILD_ORDER)?.list()?;
            let merged = list_merger(&comp_co.items(), &inst_co.items());
            self.set(node, CHILD_ORDER, Val::List(SL::new(merged)))?;
        }
        let (children, _) = timed!(self, "children", self.children(&Val::Str(real.clone()), true))?;
        for child_src in children {
            let mut target: Vec<S> = namespace.items().clone();
            target.push(ns_last(&child_src));
            let tgt_path = ns_to_path(&target);
            match self.lookup(&tgt_path) {
                Some(found) => {
                    let ex = self.get(Some(found), INSTANCE)?;
                    if !ex.eq_str("") {
                        self.set(found, INSTANCE, Val::Str(child_src.clone()))?;
                    }
                }
                None => to_do.push((SL::new(target), child_src.clone(), tgt_path)),
            }
        }
        to_do.sort_by_key(|item| item.0.items().len());
        Ok(to_do)
    }

    fn find_instance_cycle(&mut self, node_path: &S, node: Cid) -> Res<Option<Vec<S>>> {
        let mut chain: Vec<S> = vec![node_path.clone()];
        let mut node = node;
        let mut path = node_path.clone();
        loop {
            let inst = self.get(Some(node), INSTANCE)?;
            if !inst.truthy() || inst.is_world() {
                return Ok(None);
            }
            let inst = inst.string()?;
            let inst = expand_relative(&inst, &path).unwrap_or_else(|| new_s(""));
            let closes = *inst == **node_path || is_ancestor(node_path, &inst);
            if closes && chain.len() == 1 && *inst != **node_path {
                return Ok(None);
            }
            if closes {
                chain.push(inst);
                return Ok(Some(chain));
            }
            if chain.iter().any(|c| **c == *inst) {
                return Ok(None);
            }
            match self.lookup(&inst) {
                Some(n) => node = n,
                None => return Ok(None),
            }
            chain.push(inst.clone());
            path = inst;
        }
    }

    fn break_instance_cycles(&mut self) -> Res<()> {
        let table: Vec<Cid> = self.node_table.iter().map(|(_, c)| *c).collect();
        for node in table {
            if !self.get(Some(node), INSTANCE)?.truthy() {
                continue;
            }
            let path = self.node_path(node)?;
            if let Some(chain) = self.find_instance_cycle(&path, node)? {
                let joined: Vec<&str> = chain.iter().map(|s| &**s).collect();
                self.log("error", format!("Circular instance: {}. Ignoring the instance path on {}.",
                                          joined.join(" -> "), path), vec![path.to_string()]);
                let target = match self.lookup(&path) {
                    Some(t) => t,
                    None => return fallback("a cycle on a node not in the comp layer"),
                };
                self.set(target, INSTANCE, Val::None)?;
            }
        }
        Ok(())
    }

    fn get_instance_sources(&mut self, node: Cid, trace: &mut Vec<Cid>) -> Res<()> {
        let mut node = node;
        loop {
            let inst = match self.lookup_attr(node, INSTANCE)? {
                None => return Ok(()),
                Some(v) => v,
            };
            let n = match &inst {
                Val::Str(s) => self.lookup(s),
                Val::None => None,
                _ => return fallback("an instance path that is not a string"),
            };
            match n {
                Some(n) if !trace.contains(&n) => {
                    trace.push(n);
                    node = n;
                }
                _ => return Ok(()),
            }
        }
    }

    /// sort_instances: the nodes in their order.
    fn sort_instances(&mut self, deep: bool) -> Res<Vec<Cid>> {
        let nodes: Vec<Cid> = self.node_table.iter().map(|(_, c)| *c).collect();
        let mut items: Vec<(usize, usize)> = Vec::with_capacity(nodes.len());
        let mut src: HashMap<S, usize> = HashMap::new();
        for (i, &node) in nodes.iter().enumerate() {
            let mut trace = Vec::new();
            self.get_instance_sources(node, &mut trace)?;
            let path = self.node_path(node)?;
            // A later item with the same path replaces the earlier one, as
            // the dict does; paths are unique in the comp layer anyway.
            src.insert(path, i);
            items.push((trace.len(), i));
        }
        items.sort_by_key(|item| item.0);
        let sorted: Vec<usize> = items.iter().map(|item| item.1).collect();
        if !deep {
            return Ok(sorted.iter().map(|&i| nodes[i]).collect());
        }
        // The moves of nxt_layer.RankedList, which behaves as a list.
        let mut ranked = Ranked::new(&sorted);
        let mut offsets: HashMap<S, usize> = HashMap::new();
        for &item in &sorted {
            let node = nodes[item];
            let path = self.node_path(node)?;
            let real = match self.checked_instance(&path, node)? {
                Some(r) => r,
                None => continue,
            };
            let src_item = match src.get(&real) {
                Some(&s) => s,
                None => continue,
            };
            let idx = ranked.index(src_item);
            let offset = *offsets.get(&real).unwrap_or(&1);
            ranked.remove(item);
            ranked.insert(idx + offset, item);
            offsets.insert(real, offset + 1);
        }
        Ok(ranked.to_list().iter().map(|&i| nodes[i]).collect())
    }

    pub fn comp_proxies(&mut self, node_count: usize) -> Res<(i64, usize)> {
        let mut node_count = node_count as i64;
        let mut new_node_count: i64 = -1;
        let mut proxy_count: i64 = 0;
        let mut loops = 0;
        let mut implied_proxies: Vec<(Option<Cid>, S, SL)> = Vec::new();
        while node_count != new_node_count {
            new_node_count = node_count;
            loops += 1;
            let mut added = 0;
            let mut to_do = Vec::new();
            timed!(self, "break_instance_cycles", self.break_instance_cycles())?;
            let deep = timed!(self, "sort_instances deep", self.sort_instances(true))?;
            for node in deep {
                let path = self.node_path(node)?;
                let ns = SL::new(str_path_to_ns(&path));
                to_do.extend(timed!(self, "discover_proxies", self.discover_proxies(&path, node, &ns))?);
            }
            for (tgt_ns, src_path, tgt_path) in to_do {
                let new = timed!(self, "create_instance_node",
                                 self.create_instance_node(&src_path, &tgt_path, tgt_ns.clone()))?;
                if new.is_none() {
                    implied_proxies.push((self.lookup(&tgt_path), tgt_path.clone(), tgt_ns));
                }
                node_count += 1;
                added += 1;
            }
            proxy_count += added;
        }
        for (node, path, ns) in implied_proxies {
            proxy_count -= 1;
            self.remove_node_from_comp_layer(&path, node, &ns)?;
        }
        Ok((proxy_count, loops))
    }

    fn add_base_class(&mut self, node: Cid, base: Cid) -> Res<()> {
        let mut bases = self.classes[node].bases.clone();
        bases.push(base);
        self.set_bases(node, bases)
    }

    fn safe_mro_add_base_class(&mut self, node: Cid, base: Cid) -> Res<()> {
        let current = self.classes[node].bases.clone();
        if current.contains(&base) {
            return Ok(());
        }
        let incoming = self.classes[base].bases.clone();
        let mut safe = current.clone();
        let mut changed = false;
        for &c in &current {
            for &b in &incoming {
                let mro = self.mro(b)?;
                if mro.contains(&c) {
                    if let Some(pos) = safe.iter().position(|&x| x == c) {
                        safe.remove(pos);
                        changed = true;
                    }
                }
            }
        }
        if changed {
            safe.push(base);
            if safe != self.classes[node].bases {
                self.set_bases(node, safe)?;
            }
            Ok(())
        } else {
            self.add_base_class(node, base)
        }
    }

    pub fn post_proxy_comp(&mut self) -> Res<(usize, usize)> {
        let mut roots: HashSet<Cid> = HashSet::new();
        let mut root_count = 0;
        let mut total_count = 0;
        let sorted = self.sort_instances(false)?;
        for (arc_idx, parent_arc) in [true, false].iter().enumerate() {
            let arc = if *parent_arc { "parent" } else { "instance" };
            let overload: &[u8] = if *parent_arc { &[] } else { &INSTANCE_OVERLOAD };
            let mut parent_bases: Vec<(usize, Cid, Cid)> = Vec::new();
            for &node in &sorted {
                let node_path = self.node_path(node)?;
                let base_path: Val;
                if *parent_arc {
                    let mut pp = self.must(node, PARENT_PATH)?;
                    if !pp.truthy() {
                        continue;
                    }
                    if self.lookup_val(&pp)?.is_none() {
                        while !pp.is_world() {
                            pp = Val::Str(get_parent_path(&pp.string()?));
                            if self.lookup_val(&pp)?.is_some() {
                                break;
                            }
                        }
                    }
                    base_path = pp;
                } else {
                    base_path = match self.lookup_attr(node, INSTANCE)? {
                        None => continue,
                        Some(v) => v,
                    };
                    if base_path.is_world() {
                        continue;
                    }
                }
                let base = match self.lookup_val(&base_path)? {
                    Some(b) => b,
                    None => {
                        if base_path.truthy() && !base_path.is_world() {
                            let bp = base_path.string()?;
                            self.log("error", format!("Unable to find {} node for {}", arc, node_path),
                                     vec![node_path.to_string()]);
                            // Three values for two places, as in Stage.
                            self.log("debug", format!("requested {} {}", arc, bp), Vec::new());
                        }
                        continue;
                    }
                };
                if *parent_arc {
                    let bp = base_path.string()?;
                    let listed = match self.cached_children.get_str(&bp) {
                        Some(e) => e.paths.iter().any(|p| **p == *node_path),
                        None => false,
                    };
                    if !listed {
                        self.add_child_to_child_cache(&base_path, &node_path, node)?;
                    }
                }
                for &attr in overload {
                    let has = self.get(Some(node), attr)?.has_opinion();
                    let value = self.get(Some(base), attr)?;
                    if has {
                        continue;
                    }
                    let src_layer = self.must(base, SOURCE_LAYER)?;
                    self.set(node, attr, value)?;
                    self.set(node, meta(attr), Val::tuple(src_layer, Val::Str(node_path.clone())))?;
                }
                if *parent_arc {
                    parent_bases.push((path_depth(&node_path), node, base));
                } else {
                    timed!(self, "safe_mro_add_base_class", self.safe_mro_add_base_class(node, base))?;
                }
                if self.must(node, PARENT_PATH)?.is_world() && roots.insert(node) {
                    root_count += 1;
                }
                if arc_idx == 0 {
                    total_count += 1;
                }
            }
            parent_bases.sort_by_key(|item| item.0);
            for (_, node, base) in parent_bases {
                self.add_base_class(node, base)?;
            }
        }
        Ok((root_count, total_count))
    }

    // Making it real ----------------------------------------------------------------

    fn out_s(&self, py: Python<'_>, s: &S, made: &mut HashMap<usize, PyObject>) -> PyObject {
        let p = s_ptr(s);
        if let Some(o) = self.objects.get(&p) {
            return o.clone_ref(py);
        }
        if one_object(s) {
            return PyString::new(py, s).into_any().unbind();
        }
        if let Some(o) = made.get(&p) {
            return o.clone_ref(py);
        }
        let o = PyString::new(py, s).into_any().unbind();
        made.insert(p, o.clone_ref(py));
        o
    }

    fn out_list(&self, py: Python<'_>, l: &SL, made: &mut HashMap<usize, PyObject>) -> PyResult<PyObject> {
        let p = l.ptr();
        if let Some(o) = self.objects.get(&p) {
            return Ok(o.clone_ref(py));
        }
        if let Some(o) = made.get(&p) {
            return Ok(o.clone_ref(py));
        }
        let items: Vec<PyObject> = l.items().iter().map(|s| self.out_s(py, s, made)).collect();
        let o = PyList::new(py, items)?.into_any().unbind();
        made.insert(p, o.clone_ref(py));
        Ok(o)
    }

    fn out_strs(&self, py: Python<'_>, items: &[S], made: &mut HashMap<usize, PyObject>) -> PyResult<PyObject> {
        let items: Vec<PyObject> = items.iter().map(|s| self.out_s(py, s, made)).collect();
        Ok(PyList::new(py, items)?.into_any().unbind())
    }

    fn out_val(&self, py: Python<'_>, v: &Val, made: &mut HashMap<usize, PyObject>) -> PyResult<PyObject> {
        Ok(match v {
            Val::None => py.None(),
            Val::Bool(b) => PyBool::new(py, *b).to_owned().into_any().unbind(),
            Val::Str(s) => self.out_s(py, s, made),
            Val::List(l) => self.out_list(py, l, made)?,
            Val::Tuple(t) => {
                let p = Rc::as_ptr(t) as *const u8 as usize;
                if let Some(o) = self.objects.get(&p) {
                    return Ok(o.clone_ref(py));
                }
                if let Some(o) = made.get(&p) {
                    return Ok(o.clone_ref(py));
                }
                let a = self.out_val(py, &t.0, made)?;
                let b = self.out_val(py, &t.1, made)?;
                let o = PyTuple::new(py, [a, b])?.into_any().unbind();
                made.insert(p, o.clone_ref(py));
                o
            }
            Val::Other(o) => {
                let p = Rc::as_ptr(o) as *const u8 as usize;
                match self.objects.get(&p) {
                    Some(obj) => obj.clone_ref(py),
                    None => return Err(pyo3::exceptions::PyValueError::new_err(
                        "fallback: a value without its object")),
                }
            }
        })
    }

    /// Make the classes, each once with its final bases, and the comp
    /// layer's tables and caches, as Python objects.
    pub fn make(&self, py: Python<'_>, args: &MakeArgs) -> PyResult<PyObject> {
        // Python never changes a list it was given; check that nothing here
        // did either, since it would have to be changed in Python too.
        for (list, items) in &self.read_lists {
            let now = list.items();
            if now.len() != items.len() || now.iter().zip(items.iter()).any(|(a, b)| !Rc::ptr_eq(a, b)) {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "fallback: a list read in was changed"));
            }
        }
        let mut objs: HashMap<usize, PyObject> = HashMap::new();
        // Bases before the classes made from them.
        let n = self.classes.len();
        let mut order: Vec<Cid> = Vec::with_capacity(n);
        let mut state = vec![0u8; n];
        for cid in 0..n {
            let kind = self.classes[cid].kind;
            if kind == Kind::Node || kind == Kind::Spec || state[cid] != 0 {
                continue;
            }
            let mut stack = vec![(cid, false)];
            while let Some((c, done)) = stack.pop() {
                if done {
                    state[c] = 2;
                    order.push(c);
                    continue;
                }
                if state[c] != 0 {
                    continue;
                }
                state[c] = 1;
                stack.push((c, true));
                for &b in &self.classes[c].bases {
                    if b == OBJECT {
                        continue;
                    }
                    let bk = self.classes[b].kind;
                    if (bk == Kind::Comp || bk == Kind::MadeSpec) && state[b] == 0 {
                        stack.push((b, false));
                    }
                }
            }
        }
        let mut made: Vec<Option<PyObject>> = (0..n).map(|_| None).collect();
        let class_of = |cid: Cid, made: &Vec<Option<PyObject>>| -> PyObject {
            let class = &self.classes[cid];
            match class.kind {
                Kind::Node => args.node.clone_ref(py),
                Kind::Spec => args.specs[class.spec_index].clone_ref(py),
                _ => made[cid].as_ref().unwrap().clone_ref(py),
            }
        };
        let module_key = PyString::new(py, "__module__").into_any().unbind();
        let doc_key = PyString::new(py, "__doc__").into_any().unbind();
        for &cid in &order {
            let class = &self.classes[cid];
            // One dict in the order the old way ends up with: the attrs the
            // class was made with, holding their final values, then what
            // type() adds, __module__ as from nxt_node and __doc__, then the
            // attrs set on it afterwards, in the order they were first set.
            let dict = PyDict::new(py);
            for (i, (k, v)) in class.dict.iter().enumerate() {
                if i == class.n_initial {
                    dict.set_item(module_key.clone_ref(py), args.module.clone_ref(py))?;
                    dict.set_item(doc_key.clone_ref(py), py.None())?;
                }
                dict.set_item(args.keys[k as usize].clone_ref(py), self.out_val(py, v, &mut objs)?)?;
            }
            if class.dict.order.len() <= class.n_initial {
                dict.set_item(module_key.clone_ref(py), args.module.clone_ref(py))?;
                dict.set_item(doc_key.clone_ref(py), py.None())?;
            }
            let (name, bases) = if class.kind == Kind::MadeSpec {
                (args.spec_name.clone_ref(py), PyTuple::new(py, [args.node.clone_ref(py)])?)
            } else {
                let bases: Vec<PyObject> = class.bases.iter().map(|&b| class_of(b, &made)).collect();
                (args.comp_name.clone_ref(py), PyTuple::new(py, bases)?)
            };
            let cls = args.type_fn.call1(py, (name, bases, dict))?;
            made[cid] = Some(cls);
        }
        let rt = &args.return_types;
        let node_table = PyList::empty(py);
        for (ns, c) in &self.node_table {
            let ns = self.out_list(py, ns, &mut objs)?;
            node_table.append(PyList::new(py, [ns, class_of(*c, &made)])?)?;
        }
        let path_key = PyDict::new(py);
        for (p, c) in self.path_key.iter() {
            path_key.set_item(self.out_s(py, p, &mut objs), class_of(*c, &made))?;
        }
        let node_key = PyDict::new(py);
        for (c, p) in self.node_key.iter() {
            node_key.set_item(class_of(*c, &made), self.out_s(py, p, &mut objs))?;
        }
        let cache = PyDict::new(py);
        for (p, e) in self.cached_children.iter() {
            let entry = PyDict::new(py);
            entry.set_item(rt[0].clone_ref(py), PyList::new(py, e.nodes.iter().map(|c| class_of(*c, &made)))?)?;
            entry.set_item(rt[1].clone_ref(py), self.out_strs(py, &e.paths, &mut objs)?)?;
            let table = PyList::empty(py);
            for (tp, tc) in &e.table {
                table.append(PyList::new(py, [self.out_s(py, tp, &mut objs), class_of(*tc, &made)])?)?;
            }
            entry.set_item(rt[2].clone_ref(py), table)?;
            let names = PyDict::new(py);
            for (nm, c) in e.names.iter() {
                names.set_item(self.out_s(py, nm, &mut objs), class_of(*c, &made))?;
            }
            entry.set_item(rt[3].clone_ref(py), names)?;
            cache.set_item(self.out_s(py, p, &mut objs), entry)?;
        }
        let implied = PyDict::new(py);
        for (p, v) in self.cached_implied.iter() {
            let entry = PyDict::new(py);
            entry.set_item(rt[1].clone_ref(py), self.out_strs(py, v, &mut objs)?)?;
            implied.set_item(self.out_s(py, p, &mut objs), entry)?;
        }
        let index = PyDict::new(py);
        for (p, v) in self.implied_index.iter() {
            index.set_item(self.out_s(py, p, &mut objs), self.out_strs(py, v, &mut objs)?)?;
        }
        let dirty = PyDict::new(py);
        for (p, v) in self.dirty_map.iter() {
            dirty.set_item(self.out_s(py, p, &mut objs), self.out_strs(py, v, &mut objs)?)?;
        }
        let logs = PyList::empty(py);
        for log in &self.logs {
            logs.append(PyTuple::new(py, [
                PyString::new(py, log.level).into_any().unbind(),
                PyString::new(py, &log.msg).into_any().unbind(),
                PyList::new(py, log.links.iter().map(|l| PyString::new(py, l)))?.into_any().unbind(),
            ])?)?;
        }
        let calls = PyList::empty(py);
        for (layer, path) in &self.layer_calls {
            calls.append(PyTuple::new(py, [PyString::new(py, layer), PyString::new(py, path)])?)?;
        }
        let out = PyTuple::new(py, [
            node_table.into_any().unbind(),
            path_key.into_any().unbind(),
            node_key.into_any().unbind(),
            cache.into_any().unbind(),
            implied.into_any().unbind(),
            PyBool::new(py, self.bulk_valid).to_owned().into_any().unbind(),
            index.into_any().unbind(),
            PyBool::new(py, self.implied_valid).to_owned().into_any().unbind(),
            self.implied_len.into_pyobject(py)?.into_any().unbind(),
            dirty.into_any().unbind(),
            logs.into_any().unbind(),
            calls.into_any().unbind(),
        ])?;
        Ok(out.into_any().unbind())
    }
}

/// What making the comp's objects needs from Python.
pub struct MakeArgs {
    pub keys: Vec<Py<PyAny>>,
    pub type_fn: Py<PyAny>,
    pub node: Py<PyAny>,
    pub specs: Vec<Py<PyAny>>,
    pub module: Py<PyAny>,
    pub spec_name: Py<PyAny>,
    pub comp_name: Py<PyAny>,
    pub return_types: Vec<Py<PyAny>>,
}
