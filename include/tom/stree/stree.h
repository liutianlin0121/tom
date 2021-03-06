#ifndef STREE_H
#define STREE_H

#include "../tom.h"

namespace stree {

typedef uint32_t nidx_t;                   // the index "pointer" type to be used

//nidx_t BitFlags:
constexpr nidx_t VALID    =   1 << 31;
constexpr nidx_t INTERNAL =   1 << 30;
constexpr nidx_t COLOR    =   1 << 29;
constexpr nidx_t INDEX    = ~(7 << 29);
constexpr nidx_t ROOT = VALID | INTERNAL;

typedef tom::Sequence Sequence;
typedef tom::Symbol Symbol;

// forward declarations
class STree;
class Node;
class EdgeNode;
class PathNode;
class Position;
class PrefixIterator;
class PostfixIterator;
class DFSIterator;

SWIGCODE(%ignore nodelete;)
/** Hack needed to convert a normal pointer to a `std::shared_ptr` safely */
struct nodelete {
    template <typename T>
    void operator()( T * ) {}
};

} // namespace stree

SWIGCODE(%shared_ptr(stree::STree);)
SWIGCODE(%shared_ptr(std::vector<stree::nidx_t>);)
SWIGCODE(%template(NidxVector) std::vector<stree::nidx_t>;)

#include "RBTree.h"
#include "STreeCore.h"
#include "STreeNode.h"
#include "STreeIterators.h"
#include "STreeCore.cpp"

#endif // STREE_H
